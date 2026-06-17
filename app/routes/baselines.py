import uuid
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.services import (
    list_baselines, get_baseline, create_baseline, update_baseline, delete_baseline, delete_all_baselines,
    list_parameters,
)
from app.schemas import BaselineConfigCreate
from app.template_setup import templates

router = APIRouter(prefix="/baseline", tags=["baseline"])


@router.get("", response_class=HTMLResponse)
async def baseline_list(request: Request):
    baselines = list_baselines()
    return templates.TemplateResponse(
        request, "baseline.html", {"request": request, "baselines": baselines}
    )


@router.get("/new", response_class=HTMLResponse)
async def baseline_new_form(request: Request):
    param_defs = list_parameters()
    return templates.TemplateResponse(
        request,
        "baseline_form.html",
        {
            "request": request,
            "baseline": None,
            "param_defs": param_defs,
            "server_types": ["web", "db", "app"],
            "os_choices": ["linux", "windows"],
        },
    )


@router.post("/new")
async def baseline_create(
    server_type: str = Form(...),
    os_family: str = Form(...),
    os_version: str = Form(""),
    region: str = Form(""),
    parameter_definition_id: str = Form(...),
    expected_value: str = Form(...),
    is_critical: str = Form("off"),
):
    try:
        param_uuid = uuid.UUID(parameter_definition_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Invalid parameter definition ID")
    data = BaselineConfigCreate(
        server_type=server_type.lower(),
        os_family=os_family.lower(),
        os_version=os_version or None,
        region=region or None,
        parameter_definition_id=param_uuid,
        expected_value=expected_value,
        is_critical=is_critical == "on",
    )
    create_baseline(data)
    return RedirectResponse(url="/baseline", status_code=303)


@router.get("/{baseline_id}/edit", response_class=HTMLResponse)
async def baseline_edit_form(request: Request, baseline_id: uuid.UUID):
    baseline = get_baseline(baseline_id)
    if not baseline:
        raise HTTPException(status_code=404, detail="Baseline not found")
    param_defs = list_parameters()
    return templates.TemplateResponse(
        request,
        "baseline_form.html",
        {
            "request": request,
            "baseline": baseline,
            "param_defs": param_defs,
            "server_types": ["web", "db", "app"],
            "os_choices": ["linux", "windows"],
        },
    )


@router.post("/{baseline_id}/edit")
async def baseline_edit(
    request: Request,
    baseline_id: uuid.UUID,
    server_type: str = Form(...),
    os_family: str = Form(...),
    os_version: str = Form(""),
    region: str = Form(""),
    parameter_definition_id: str = Form(...),
    expected_value: str = Form(...),
    is_critical: str = Form("off"),
):
    try:
        param_uuid = uuid.UUID(parameter_definition_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Invalid parameter definition ID")
    data = BaselineConfigCreate(
        server_type=server_type.lower(),
        os_family=os_family.lower(),
        os_version=os_version or None,
        region=region or None,
        parameter_definition_id=param_uuid,
        expected_value=expected_value,
        is_critical=is_critical == "on",
    )
    updated = update_baseline(baseline_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Baseline not found")
    return RedirectResponse(url="/baseline", status_code=303)


@router.post("/{baseline_id}/delete")
async def baseline_delete(
    baseline_id: uuid.UUID,
):
    deleted = delete_baseline(baseline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Baseline not found")
    return RedirectResponse(url="/baseline", status_code=303)


@router.post("/delete-all")
async def baseline_delete_all():
    count = delete_all_baselines()
    return RedirectResponse(url="/baseline", status_code=303)
