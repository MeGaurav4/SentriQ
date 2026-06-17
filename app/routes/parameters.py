import uuid
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from app.services import (
    list_parameters,
    get_parameter,
    create_parameter,
    update_parameter,
    toggle_parameter,
    delete_parameter,
    delete_all_parameters,
)
from app.schemas import ParameterDefinitionCreate, ParameterDefinitionUpdate
from app.template_setup import templates

router = APIRouter(prefix="/parameters", tags=["parameters"])


@router.get("", response_class=HTMLResponse)
async def parameter_list(request: Request, os_family: Optional[str] = None):
    params = list_parameters(os_family)
    return templates.TemplateResponse(
        request,
        "parameters.html",
        {"request": request, "parameters": params, "os_filter": os_family},
    )


@router.get("/new", response_class=HTMLResponse)
async def parameter_new_form(request: Request):
    return templates.TemplateResponse(
        request,
        "parameter_form.html",
        {"request": request, "parameter": None, "os_choices": ["linux", "windows"]},
    )


@router.post("/new")
async def parameter_create(
    name: str = Form(...),
    display_name: str = Form(...),
    os_family: str = Form(...),
    data_type: str = Form("string"),
    category: str = Form("system"),
    is_active: str = Form("off"),
    sort_order: str = Form("0"),
    default_severity: str = Form("warning"),
    help_text: str = Form(""),
):
    try:
        sort_order_int = int(sort_order)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="sort_order must be an integer")
    data = ParameterDefinitionCreate(
        name=name,
        display_name=display_name,
        os_family=os_family.lower(),
        data_type=data_type,
        category=category,
        is_active=is_active == "on",
        sort_order=sort_order_int,
        default_severity=default_severity,
        help_text=help_text or None,
    )
    create_parameter(data)
    return RedirectResponse(url="/parameters", status_code=303)


@router.get("/{param_id}/edit", response_class=HTMLResponse)
async def parameter_edit_form(request: Request, param_id: uuid.UUID):
    param = get_parameter(param_id)
    if not param:
        raise HTTPException(status_code=404, detail="Parameter not found")
    return templates.TemplateResponse(
        request,
        "parameter_form.html",
        {
            "request": request,
            "parameter": param,
            "os_choices": ["linux", "windows"],
        },
    )


@router.post("/{param_id}/edit")
async def parameter_edit(
    request: Request,
    param_id: uuid.UUID,
    display_name: str = Form(...),
    os_family: str = Form(...),
    data_type: str = Form("string"),
    category: str = Form("system"),
    is_active: str = Form("off"),
    sort_order: str = Form("0"),
    default_severity: str = Form("warning"),
    help_text: str = Form(""),
):
    try:
        sort_order_int = int(sort_order)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="sort_order must be an integer")
    data = ParameterDefinitionUpdate(
        display_name=display_name,
        os_family=os_family.lower(),
        data_type=data_type,
        category=category,
        is_active=is_active == "on",
        sort_order=sort_order_int,
        default_severity=default_severity,
        help_text=help_text or None,
    )
    param = update_parameter(param_id, data)
    if not param:
        raise HTTPException(status_code=404, detail="Parameter not found")
    return RedirectResponse(url="/parameters", status_code=303)


@router.post("/{param_id}/toggle")
async def parameter_toggle(
    param_id: uuid.UUID,
):
    param = toggle_parameter(param_id)
    if not param:
        raise HTTPException(status_code=404, detail="Parameter not found")
    return RedirectResponse(url="/parameters", status_code=303)


@router.post("/{param_id}/delete")
async def parameter_delete(
    param_id: uuid.UUID,
):
    deleted = delete_parameter(param_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Parameter not found")
    return RedirectResponse(url="/parameters", status_code=303)


@router.post("/delete-all")
async def parameter_delete_all():
    count = delete_all_parameters()
    return RedirectResponse(url="/parameters", status_code=303)
