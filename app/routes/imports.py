import os
import uuid
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from app.parameter_import import run_import, list_imports
from app.baseline_import import run_baseline_import
from app.drift_engine import run_curated_drift_detection
from app.excel_export import generate_excel
from app.csv_export import generate_powerbi_csv
from app.template_setup import templates

router = APIRouter(prefix="/import", tags=["import"])

ALLOWED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",
}

DEFAULT_DROP = "data/reports"


def _save_upload(file: UploadFile) -> str:
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")
    filename = os.path.basename(file.filename)
    drop_dir = os.getenv("EXCEL_OUTPUT_PATH", DEFAULT_DROP)
    os.makedirs(drop_dir, exist_ok=True)
    dest = os.path.join(drop_dir, f"{uuid.uuid4()}_{filename}")
    content = file.file.read()
    with open(dest, "wb") as f:
        f.write(content)
    return dest, filename


@router.get("", response_class=HTMLResponse)
async def import_page(request: Request):
    history = list_imports(limit=20)
    return templates.TemplateResponse(
        request,
        "import.html",
        {"request": request, "result": None, "history": history},
    )


@router.post("/parameters", response_class=HTMLResponse)
async def import_parameters(
    request: Request,
    file: UploadFile = File(...),
    os_family: str = Form(...),
):
    dest, filename = _save_upload(file)
    try:
        result = run_import(dest, filename, os_family)
        if result["errors"] == 0 and result["success"] > 0:
            report_id = run_curated_drift_detection()
            generate_excel(report_id, os.getenv("EXCEL_OUTPUT_PATH"))
            generate_powerbi_csv(report_id, os.getenv("CSV_OUTPUT_PATH"))
        status = "success" if result["errors"] == 0 else "warning"
    except ValueError as e:
        result = {"error": str(e)}
        status = "danger"

    history = list_imports(limit=20)
    return templates.TemplateResponse(
        request,
        "import.html",
        {
            "request": request,
            "result": result,
            "status": status,
            "history": history,
            "active_tab": "parameters",
        },
    )


@router.post("/baselines", response_class=HTMLResponse)
async def import_baselines(
    request: Request,
    file: UploadFile = File(...),
    os_family: str = Form(...),
):
    dest, filename = _save_upload(file)
    try:
        result = run_baseline_import(dest, filename, os_family_override=os_family)
        if result["errors"] == 0 and result["success"] > 0:
            report_id = run_curated_drift_detection()
            generate_excel(report_id, os.getenv("EXCEL_OUTPUT_PATH"))
            generate_powerbi_csv(report_id, os.getenv("CSV_OUTPUT_PATH"))
        status = "success" if result["errors"] == 0 else "warning"
    except ValueError as e:
        result = {"error": str(e)}
        status = "danger"

    history = list_imports(limit=20)
    return templates.TemplateResponse(
        request,
        "import.html",
        {
            "request": request,
            "result": result,
            "status": status,
            "history": history,
            "active_tab": "baselines",
        },
    )
