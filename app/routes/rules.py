import uuid
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.services import (
    list_rules, get_rule, create_rule, update_rule, delete_rule, delete_all_rules,
    list_parameters,
)
from app.schemas import RuleCreate
from app.template_setup import templates

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_class=HTMLResponse)
async def rules_list(request: Request):
    rules = list_rules()
    param_defs = list_parameters()
    param_map = {str(p.id): p for p in param_defs}
    return templates.TemplateResponse(
        request, "rules.html",
        {"request": request, "rules": rules, "param_map": param_map},
    )


@router.get("/new", response_class=HTMLResponse)
async def rules_new_form(request: Request):
    param_defs = list_parameters()
    return templates.TemplateResponse(
        request, "rule_form.html",
        {"request": request, "rule": None, "param_defs": param_defs},
    )


@router.post("/new")
async def rules_create(
    dc_name: str = Form(...),
    parameter_definition_id: str = Form(...),
    expected_value: str = Form(...),
):
    try:
        param_uuid = uuid.UUID(parameter_definition_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Invalid parameter definition")
    data = RuleCreate(
        dc_name=dc_name.strip(),
        parameter_definition_id=param_uuid,
        expected_value=expected_value,
    )
    create_rule(data)
    return RedirectResponse(url="/rules", status_code=303)


@router.get("/{rule_id}/edit", response_class=HTMLResponse)
async def rules_edit_form(request: Request, rule_id: uuid.UUID):
    rule = get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    param_defs = list_parameters()
    return templates.TemplateResponse(
        request, "rule_form.html",
        {"request": request, "rule": rule, "param_defs": param_defs},
    )


@router.post("/{rule_id}/edit")
async def rules_edit(
    rule_id: uuid.UUID,
    dc_name: str = Form(...),
    parameter_definition_id: str = Form(...),
    expected_value: str = Form(...),
):
    try:
        param_uuid = uuid.UUID(parameter_definition_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Invalid parameter definition")
    data = RuleCreate(
        dc_name=dc_name.strip(),
        parameter_definition_id=param_uuid,
        expected_value=expected_value,
    )
    updated = update_rule(rule_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found")
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/{rule_id}/delete")
async def rules_delete(rule_id: uuid.UUID):
    deleted = delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/delete-all")
async def rules_delete_all():
    delete_all_rules()
    return RedirectResponse(url="/rules", status_code=303)
