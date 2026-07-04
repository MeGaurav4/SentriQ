import os
import uuid
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse

from app.db import get_session
from sqlalchemy import select, func, case
from app.models import Server, DriftReport, DriftFinding, ServerParameter, ParameterDefinition, BaselineConfig
from app.drift_engine import run_curated_drift_detection
from app.excel_export import generate_excel
from app.csv_export import generate_powerbi_csv

from app.services import update_server_dc
from app.routes.parameters import router as parameters_router
from app.routes.imports import router as imports_router
from app.routes.baselines import router as baselines_router
from app.routes.rules import router as rules_router
from app.template_setup import templates

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="SentriQ Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.datatables.net; script-src 'self' 'unsafe-inline' https://code.jquery.com https://cdn.datatables.net https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:; connect-src 'self';"
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.include_router(parameters_router)
app.include_router(imports_router)
app.include_router(baselines_router)
app.include_router(rules_router)


REQUIRED_ENV_VARS = ["DB_URL", "EXCEL_OUTPUT_PATH", "CSV_OUTPUT_PATH"]
for var in REQUIRED_ENV_VARS:
    if not os.getenv(var):
        print(f"CRITICAL ERROR: Environment variable {var} is missing.")
        raise SystemExit(1)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, page: int = 1, per_page: int = 50, export: int = 0):
    with get_session() as session:
        report = session.execute(
            select(DriftReport).order_by(DriftReport.generated_at.desc()).limit(1)
        ).scalar_one_or_none()

        total_servers = session.execute(select(func.count(Server.id))).scalar() or 0
        if total_servers == 0:
            return templates.TemplateResponse(
                request,
                "index.html",
                {
                    "request": request,
                    "servers": [],
                    "stats": {
                        "total_servers": 0,
                        "compliant_percent": 0,
                        "critical_count": report.critical_count if report else 0,
                        "changes_24h": 0,
                    },
                    "latest_report_id": report.id if report else None,
                    "page": 1,
                    "per_page": 50,
                    "total_pages": 0,
                },
            )

        page = max(1, page)
        per_page = max(1, min(per_page, 200))
        offset = (page - 1) * per_page
        total_pages = (total_servers + per_page - 1) // per_page

        servers = session.execute(
            select(Server).order_by(Server.hostname).offset(offset).limit(per_page)
        ).scalars().all()

        server_ids = [s.id for s in servers]

        findings_by_server = {}
        if report:
            all_findings = session.execute(
                select(DriftFinding)
                .where(
                    DriftFinding.report_id == report.id,
                    DriftFinding.server_id.in_(server_ids),
                )
            ).scalars().all()

            for f in all_findings:
                findings_by_server.setdefault(f.server_id, []).append(f)

        servers_data = []
        for server in servers:
            sid = server.id
            s_findings = findings_by_server.get(sid, [])

            severity = "OK"
            if s_findings:
                if any(f.severity == "critical" for f in s_findings):
                    severity = "CRITICAL"
                elif any(f.severity == "warning" for f in s_findings):
                    severity = "WARNING"

            servers_data.append({
                "hostname": server.hostname,
                "server_type": server.server_type,
                "os_version": server.os_version,
                "last_seen": server.last_seen,
                "status": severity,
                "drift_count": sum(1 for f in s_findings if f.severity in ("critical", "warning")),
                "changes_24h": 0,
            })

        stats = {
            "total_servers": total_servers,
            "compliant_percent": 0,
            "critical_count": report.critical_count if report else 0,
            "changes_24h": 0,
        }

        if report:
            stats["compliant_percent"] = (
                round((report.compliant_count / report.total_servers * 100), 1)
                if report.total_servers > 0
                else 0
            )

        resp = templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "servers": servers_data,
                "stats": stats,
                "latest_report_id": report.id if report else None,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
            },
        )
        if export:
            resp.headers["Content-Disposition"] = "attachment; filename=sentriq-dashboard.html"
        return resp


@app.get("/server/{hostname}", response_class=HTMLResponse)
async def server_detail(request: Request, hostname: str):
    with get_session() as session:
        server = session.execute(
            select(Server).where(Server.hostname == hostname.lower())
        ).scalar_one_or_none()
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        report = session.execute(
            select(DriftReport).where(DriftReport.source == "curated")
            .order_by(DriftReport.generated_at.desc()).limit(1)
        ).scalar_one_or_none()

        baseline_findings = []
        previous_findings = []
        if report:
            findings = (
                session.execute(
                    select(DriftFinding).where(
                        DriftFinding.report_id == report.id,
                        DriftFinding.server_id == server.id,
                    )
                )
                .scalars()
                .all()
            )
            baseline_findings = [f for f in findings if f.drift_type == "vs_baseline"]
            previous_findings = [f for f in findings if f.drift_type == "vs_previous"]

        scan_history = []
        if report:
            recent_reports = (
                session.execute(
                    select(DriftReport).where(
                        DriftReport.source == "curated",
                        DriftReport.id.in_(
                            select(DriftFinding.report_id).where(
                                DriftFinding.server_id == server.id
                            ).distinct()
                        )
                    )
                    .order_by(DriftReport.generated_at.desc())
                    .limit(10)
                )
                .scalars()
                .all()
            )
            for r in recent_reports:
                r_findings = session.execute(
                    select(DriftFinding).where(
                        DriftFinding.report_id == r.id,
                        DriftFinding.server_id == server.id,
                    )
                ).scalars().all()
                crit = sum(1 for f in r_findings if f.severity == "critical")
                warn = sum(1 for f in r_findings if f.severity == "warning")
                info = sum(1 for f in r_findings if f.severity == "info")
                overall = "CRITICAL" if crit > 0 else ("WARNING" if warn > 0 else "OK")
                scan_history.append({
                    "scanned_at": r.generated_at,
                    "status": overall,
                    "params_checked": len(r_findings),
                    "drift_count": crit + warn,
                })

        curated_params = (
            session.execute(
                select(ServerParameter, ParameterDefinition)
                .join(ParameterDefinition, ServerParameter.parameter_definition_id == ParameterDefinition.id)
                .where(ServerParameter.server_id == server.id)
                .order_by(ServerParameter.collected_at.desc())
                .limit(50)
            )
            .all()
        )

        all_server_findings = baseline_findings + previous_findings
        status_summary = {
            "total": len(all_server_findings),
            "critical": sum(1 for f in all_server_findings if f.severity == "critical"),
            "warning": sum(1 for f in all_server_findings if f.severity == "warning"),
            "info": sum(1 for f in all_server_findings if f.severity == "info"),
        }
        if status_summary["critical"] > 0:
            status_summary["overall"] = "CRITICAL"
        elif status_summary["warning"] > 0:
            status_summary["overall"] = "WARNING"
        else:
            status_summary["overall"] = "OK"

        return templates.TemplateResponse(
            request,
            "server_detail.html",
            {
                "request": request,
                "server": server,
                "baseline_findings": baseline_findings,
                "previous_findings": previous_findings,
                "scan_history": scan_history,
                "curated_params": curated_params,
                "all_findings": all_server_findings,
                "status_summary": status_summary,
            },
        )


@app.post("/server/{hostname}/dc")
async def server_update_dc(hostname: str, request: Request):
    form = await request.form()
    dc = form.get("dc", "")
    server = update_server_dc(hostname, dc)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return RedirectResponse(url=f"/server/{hostname}", status_code=303)


@app.get("/curated", response_class=HTMLResponse)
async def curated_fleet(request: Request):
    with get_session() as session:
        servers = session.execute(select(Server).order_by(Server.hostname)).scalars().all()
        curated_report = session.execute(
            select(DriftReport)
            .where(DriftReport.source == "curated")
            .order_by(DriftReport.generated_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        findings_by_server = {}
        if curated_report:
            all_findings = session.execute(
                select(DriftFinding)
                .where(DriftFinding.report_id == curated_report.id)
            ).scalars().all()
            for f in all_findings:
                findings_by_server.setdefault(f.server_id, []).append(f)

        server_data = []
        for s in servers:
            findings = findings_by_server.get(s.id, [])
            severity = "OK"
            if findings:
                if any(f.severity == "critical" for f in findings):
                    severity = "CRITICAL"
                elif any(f.severity == "warning" for f in findings):
                    severity = "WARNING"
            server_data.append({
                "hostname": s.hostname,
                "server_type": s.server_type,
                "os_family": s.os_family,
                "os_version": s.os_version,
                "region": s.region,
                "findings_count": len(findings),
                "severity": severity,
            })

        return templates.TemplateResponse(
            request,
            "curated_fleet.html",
            {
                "request": request,
                "servers": server_data,
                "report": curated_report,
                "server_count": len(server_data),
            },
        )


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    import pathlib
    docs_dir = pathlib.Path("docs")
    available = []
    if docs_dir.exists():
        for f in sorted(docs_dir.iterdir()):
            if f.suffix == ".md" and f.is_file():
                available.append({"name": f.stem, "title": f.stem.replace("_", " ").title(), "path": f.name})
    available.insert(0, {"name": "README", "title": "README", "path": "../../../README.md"})
    return templates.TemplateResponse(
        request,
        "docs.html",
        {"request": request, "docs": available},
    )


@app.get("/help/raw/{name}")
async def help_raw(name: str):
    import pathlib
    if name == "README":
        path = pathlib.Path("README.md")
    else:
        path = pathlib.Path("docs") / f"{name}.md"
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    return HTMLResponse(content=path.read_text(encoding="utf-8"))


@app.get("/export/excel/{report_id}")
async def export_excel(report_id: uuid.UUID):
    try:
        excel_path = generate_excel(report_id, os.getenv("EXCEL_OUTPUT_PATH"))
        return FileResponse(excel_path, filename=os.path.basename(excel_path))
    except Exception:
        raise HTTPException(status_code=404, detail="Report not found")


@app.get("/export/csv")
async def export_csv():
    with get_session() as session:
        report = session.execute(
            select(DriftReport).order_by(DriftReport.generated_at.desc()).limit(1)
        ).scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=404, detail="No reports found")

    csv_path = generate_powerbi_csv(report.id, os.getenv("CSV_OUTPUT_PATH"))
    return FileResponse(csv_path, filename=os.path.basename(csv_path))


@app.get("/export/dashboard")
async def export_dashboard():
    from urllib.parse import urlencode
    return RedirectResponse(url="/?" + urlencode({"export": 1, "per_page": 200}), status_code=302)


@app.post("/scan")
async def trigger_scan():
    report_id = run_curated_drift_detection()
    generate_excel(report_id, os.getenv("EXCEL_OUTPUT_PATH"))
    generate_powerbi_csv(report_id, os.getenv("CSV_OUTPUT_PATH"))
    return RedirectResponse(url="/", status_code=303)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


def _build_filter_base(report_id, dc, server_type, os_family, parameter_key):
    q = select(DriftFinding).where(DriftFinding.report_id == report_id)
    q = q.join(Server, DriftFinding.server_id == Server.id)
    if dc:
        q = q.where(Server.dc == dc)
    if server_type:
        q = q.where(Server.server_type == server_type)
    if os_family:
        q = q.where(Server.os_family == os_family)
    if parameter_key:
        q = q.where(DriftFinding.parameter_key == parameter_key)
    return q


@app.get("/api/leaderboard/stats")
async def leaderboard_stats(
    request: Request,
    dc: str = "",
    server_type: str = "",
    os_family: str = "",
    parameter_key: str = "",
):
    with get_session() as session:
        report = session.execute(
            select(DriftReport).order_by(DriftReport.generated_at.desc()).limit(1)
        ).scalar_one_or_none()
        if not report:
            return {
                "compliance": {}, "top_params": [], "trend": [],
                "by_dc": [], "by_type": [], "by_os": [],
                "params_list": [], "servers": [],
            }

        report_id = report.id
        filter_q = _build_filter_base(report_id, dc, server_type, os_family, parameter_key)
        all_findings = session.execute(filter_q).scalars().all()

        params_list = sorted(set(
            f.parameter_key for f in all_findings
            if f.parameter_key and f.severity in ("critical", "warning")
        ))

        total = len(all_findings)
        critical = sum(1 for f in all_findings if f.severity == "critical")
        warning = sum(1 for f in all_findings if f.severity == "warning")
        info = sum(1 for f in all_findings if f.severity == "info")

        param_counts = {}
        for f in all_findings:
            if f.severity in ("critical", "warning"):
                key = f.parameter_key or "unknown"
                if key not in param_counts:
                    param_counts[key] = {"_key": key, "critical": 0, "warning": 0, "total": 0}
                param_counts[key][f.severity] += 1
                param_counts[key]["total"] += 1
        top_params = sorted(param_counts.values(), key=lambda x: x["total"], reverse=True)[:20]

        trend_rows = session.execute(
            select(
                DriftReport.generated_at,
                DriftReport.critical_count,
                DriftReport.warning_count,
                DriftReport.compliant_count,
                DriftReport.total_servers,
            )
            .where(DriftReport.source == "curated")
            .order_by(DriftReport.generated_at.asc())
        ).all()
        trend = [
            {
                "date": r.generated_at.strftime("%Y-%m-%d %H:%M"),
                "critical": r.critical_count,
                "warning": r.warning_count,
                "compliant": r.compliant_count,
                "total": r.total_servers,
            }
            for r in trend_rows
        ]

        filter_base_q = _build_filter_base(report_id, dc, server_type, os_family, parameter_key)

        def _agg_query(group_col, label_col, extra_cols=None):
            q = select(
                group_col,
                func.count(DriftFinding.id).label("cnt"),
                func.sum(case((DriftFinding.severity == "critical", 1), else_=0)).label("critical"),
                func.sum(case((DriftFinding.severity == "warning", 1), else_=0)).label("warning"),
                func.sum(case((DriftFinding.severity == "info", 1), else_=0)).label("info"),
            ).where(
                DriftFinding.report_id == report_id,
            )
            q = q.join(Server, DriftFinding.server_id == Server.id)
            if dc:
                q = q.where(Server.dc == dc)
            if server_type:
                q = q.where(Server.server_type == server_type)
            if os_family:
                q = q.where(Server.os_family == os_family)
            if parameter_key:
                q = q.where(DriftFinding.parameter_key == parameter_key)
            q = q.group_by(group_col).order_by(func.count(DriftFinding.id).desc())
            return session.execute(q).all()

        by_dc_raw = _agg_query(Server.dc, func.coalesce(Server.dc, "Unset"))
        by_dc = [{"dc": r.cnt if False else (r[0] or "Unset"), "critical": r.critical, "warning": r.warning, "info": r.info, "total": r.cnt} for r in by_dc_raw]

        by_type_raw = _agg_query(Server.server_type, func.coalesce(Server.server_type, "Unset"))
        by_type = [{"type": r[0] or "Unset", "critical": r.critical, "warning": r.warning, "total": r.cnt} for r in by_type_raw]

        by_os_raw = _agg_query(Server.os_family, func.coalesce(Server.os_family, "Unset"))
        by_os = [{"os": r[0] or "Unset", "critical": r.critical, "warning": r.warning, "total": r.cnt} for r in by_os_raw]

        distinct_servers = set(f.server_id for f in all_findings)
        server_count = len(distinct_servers)

        servers_critical = set()
        servers_warning = set()
        for f in all_findings:
            if f.severity == "critical":
                servers_critical.add(f.server_id)
            elif f.severity == "warning":
                servers_warning.add(f.server_id)
        servers_warning_only = servers_warning - servers_critical
        servers_clean = server_count - len(servers_critical | servers_warning)

        all_servers_q = select(Server.id)
        if dc:
            all_servers_q = all_servers_q.where(Server.dc == dc)
        if server_type:
            all_servers_q = all_servers_q.where(Server.server_type == server_type)
        if os_family:
            all_servers_q = all_servers_q.where(Server.os_family == os_family)
        total_servers = session.execute(select(func.count()).select_from(all_servers_q.subquery())).scalar() or 0
        compliant_count = max(0, total_servers - server_count - len(servers_critical | servers_warning))

        from collections import defaultdict
        _sd = defaultdict(lambda: {"critical": 0, "warning": 0, "drift_count": 0})
        filtered_server_ids = set(f.server_id for f in all_findings)
        if filtered_server_ids:
            server_info_rows = session.execute(
                select(Server).where(Server.id.in_(filtered_server_ids))
            ).scalars().all()
            server_info = {s.id: s for s in server_info_rows}
        else:
            server_info = {}
            server_info_rows = []

        for f in all_findings:
            s = server_info.get(f.server_id)
            if not s:
                continue
            sid_str = str(f.server_id)
            _sd[sid_str]["hostname"] = s.hostname
            _sd[sid_str]["type"] = s.server_type
            _sd[sid_str]["os"] = s.os_family
            _sd[sid_str]["dc"] = s.dc
            _sd[sid_str]["drift_count"] += 1
            if f.severity == "critical":
                _sd[sid_str]["critical"] += 1
            elif f.severity == "warning":
                _sd[sid_str]["warning"] += 1

        servers = sorted(
            (
                {
                    "hostname": v["hostname"],
                    "type": v["type"],
                    "os": v["os"],
                    "dc": v["dc"],
                    "drift_count": v["drift_count"],
                    "critical": v["critical"],
                    "warning": v["warning"],
                    "severity": "CRITICAL" if v["critical"] > 0 else ("WARNING" if v["warning"] > 0 else "OK"),
                }
                for v in _sd.values()
            ),
            key=lambda x: x["hostname"],
        )

        return {
            "compliance": {
                "total": total,
                "critical": critical,
                "warning": warning,
                "info": info,
                "server_count": total_servers,
                "servers_critical": len(servers_critical),
                "servers_warning": len(servers_warning_only),
                "servers_clean": servers_clean + compliant_count,
            },
            "top_params": top_params,
            "trend": trend,
            "by_dc": by_dc,
            "by_type": by_type,
            "by_os": by_os,
            "params_list": params_list,
            "servers": servers,
        }


@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request):
    with get_session() as session:
        dc_list = [r[0] for r in session.execute(select(Server.dc).distinct().where(Server.dc.isnot(None)).order_by(Server.dc)).all()]
        type_list = [r[0] for r in session.execute(select(Server.server_type).distinct().where(Server.server_type.isnot(None)).order_by(Server.server_type)).all()]
        os_list = [r[0] for r in session.execute(select(Server.os_family).distinct().where(Server.os_family.isnot(None)).order_by(Server.os_family)).all()]

    return templates.TemplateResponse(
        request,
        "leaderboard.html",
        {
            "request": request,
            "dc_list": dc_list,
            "type_list": type_list,
            "os_list": os_list,
        },
    )

