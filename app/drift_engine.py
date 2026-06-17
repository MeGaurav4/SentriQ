import uuid
from datetime import datetime, timezone
from sqlalchemy import select, text, insert as sa_insert

from app.db import get_session
from app.models import (
    Server,
    BaselineConfig,
    DriftReport,
    DriftFinding,
    ParameterDefinition,
    Rule,
)


def run_curated_drift_detection() -> uuid.UUID:
    """
    Drift detection for the curated parameter system.
    Compares server_parameters vs baseline_configs (matched by parameter_definition_id).
    Also detects vs_previous changes using window functions.
    """
    with get_session() as session:
        now = datetime.now(timezone.utc)

        all_servers = session.execute(select(Server)).scalars().all()
        all_baselines = session.execute(select(BaselineConfig)).scalars().all()
        all_rules = session.execute(select(Rule)).scalars().all()

        baseline_map = {}
        for b in all_baselines:
            baseline_map.setdefault((b.server_type.lower(), b.os_family.lower()), []).append(b)

        rule_map = {}
        for r in all_rules:
            rule_map.setdefault(r.dc_name.lower(), {})[r.parameter_definition_id] = r.expected_value

        param_def_map = {}
        all_defs = session.execute(
            select(ParameterDefinition).where(ParameterDefinition.is_active)
        ).scalars().all()
        for d in all_defs:
            param_def_map[d.id] = d

        server_ids = [s.id for s in all_servers]
        if not server_ids:
            empty_report = DriftReport(
                total_servers=0, compliant_count=0, critical_count=0,
                warning_count=0, unreachable_count=0, source="curated",
            )
            session.add(empty_report)
            session.commit()
            session.refresh(empty_report)
            return empty_report.id

        stmt = text("""
            SELECT * FROM (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY server_id, parameter_definition_id
                           ORDER BY collected_at DESC
                       ) as rn
                FROM sq_schema.server_parameters
                WHERE server_id = ANY(:server_ids)
            ) t WHERE rn <= 2
        """)
        param_rows = session.execute(stmt, {"server_ids": server_ids}).all()

        current_params = {}
        previous_params = {}
        servers_with_data = set()
        for row in param_rows:
            sid = row.server_id
            pid = row.parameter_definition_id
            if row.rn == 1:
                current_params.setdefault(sid, {})[pid] = row.parameter_value
                servers_with_data.add(sid)
            elif row.rn == 2:
                previous_params.setdefault(sid, {})[pid] = row.parameter_value

        all_findings = []
        total_servers = len(all_servers)
        unreachable_count = 0
        critical_count = 0
        warning_count = 0
        compliant_count = 0

        for server in all_servers:
            sid = server.id
            cur = current_params.get(sid, {})

            if sid not in servers_with_data:
                unreachable_count += 1
                continue

            server_is_compliant = True
            matched_def_ids = set()
            dc_rules = rule_map.get(server.dc.lower() if server.dc else "", {})

            baselines = baseline_map.get((server.server_type.lower(), server.os_family.lower()), [])
            for bp in baselines:
                def_id = bp.parameter_definition_id
                matched_def_ids.add(def_id)

                expected = dc_rules.get(def_id, bp.expected_value)

                if def_id not in cur:
                    server_is_compliant = False
                    all_findings.append(
                        DriftFinding(
                            server_id=sid,
                            parameter_definition_id=def_id,
                            category=bp.category,
                            parameter_key=bp.parameter_key,
                            baseline_value=expected,
                            current_value="KEY_NOT_PRESENT",
                            drift_type="vs_baseline",
                            severity="info",
                        )
                    )
                else:
                    cur_val = cur[def_id]
                    if expected != cur_val:
                        server_is_compliant = False
                        severity = "critical" if bp.is_critical else "warning"
                        all_findings.append(
                            DriftFinding(
                                server_id=sid,
                                parameter_definition_id=def_id,
                                category=bp.category,
                                parameter_key=bp.parameter_key,
                                baseline_value=expected,
                                current_value=cur_val,
                                drift_type="vs_baseline",
                                severity=severity,
                            )
                        )

            for def_id, cur_val in cur.items():
                if def_id not in matched_def_ids:
                    def_obj = param_def_map.get(def_id)
                    all_findings.append(
                        DriftFinding(
                            server_id=sid,
                            parameter_definition_id=def_id,
                            category=def_obj.category if def_obj else "unknown",
                            parameter_key=def_obj.name if def_obj else str(def_id),
                            baseline_value="NOT_IN_BASELINE",
                            current_value=cur_val,
                            drift_type="vs_baseline",
                            severity="info",
                        )
                    )

            prev = previous_params.get(sid, {})
            for def_id, cur_val in cur.items():
                if def_id in prev and prev[def_id] != cur_val:
                    def_obj = param_def_map.get(def_id)
                    all_findings.append(
                        DriftFinding(
                            server_id=sid,
                            parameter_definition_id=def_id,
                            category=def_obj.category if def_obj else "unknown",
                            parameter_key=def_obj.name if def_obj else str(def_id),
                            current_value=cur_val,
                            previous_value=prev[def_id],
                            drift_type="vs_previous",
                            severity="warning",
                        )
                    )

            for def_id, prev_val in prev.items():
                if def_id not in cur:
                    def_obj = param_def_map.get(def_id)
                    all_findings.append(
                        DriftFinding(
                            server_id=sid,
                            parameter_definition_id=def_id,
                            category=def_obj.category if def_obj else "unknown",
                            parameter_key=def_obj.name if def_obj else str(def_id),
                            current_value="KEY_REMOVED",
                            previous_value=prev_val,
                            drift_type="vs_previous",
                            severity="warning",
                        )
                    )

            if server_is_compliant:
                compliant_count += 1

        for f in all_findings:
            if f.severity == "critical":
                critical_count += 1
            elif f.severity == "warning":
                warning_count += 1

        report = DriftReport(
            total_servers=total_servers,
            compliant_count=compliant_count,
            critical_count=critical_count,
            warning_count=warning_count,
            unreachable_count=unreachable_count,
            source="curated",
        )
        session.add(report)
        session.flush()

        if all_findings:
            finding_dicts = []
            for f in all_findings:
                finding_dicts.append({
                    "id": uuid.uuid4(),
                    "report_id": report.id,
                    "server_id": f.server_id,
                    "parameter_definition_id": f.parameter_definition_id,
                    "category": f.category,
                    "parameter_key": f.parameter_key,
                    "baseline_value": f.baseline_value,
                    "current_value": f.current_value,
                    "previous_value": f.previous_value,
                    "drift_type": f.drift_type,
                    "severity": f.severity,
                    "first_detected_at": f.first_detected_at,
                    "resolved_at": f.resolved_at,
                })
            session.execute(sa_insert(DriftFinding.__table__), finding_dicts)

        session.commit()
        return report.id
