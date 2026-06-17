import uuid
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ParameterDefinitionCreate(BaseModel):
    name: str
    display_name: str
    os_family: str
    data_type: str = "string"
    category: str = "system"
    is_active: bool = True
    sort_order: int = 0
    default_severity: str = "warning"
    help_text: Optional[str] = None


class ParameterDefinitionUpdate(BaseModel):
    display_name: Optional[str] = None
    os_family: Optional[str] = None
    data_type: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    default_severity: Optional[str] = None
    help_text: Optional[str] = None


class ParameterDefinitionOut(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    os_family: str
    data_type: str
    category: str
    is_active: bool
    sort_order: int
    default_severity: str
    help_text: Optional[str] = None


class RegionCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RegionOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None


class ServerParameterOut(BaseModel):
    id: uuid.UUID
    server_id: uuid.UUID
    parameter_definition_id: uuid.UUID
    parameter_value: str
    collected_at: datetime
    source: str


class ServerOut(BaseModel):
    id: uuid.UUID
    hostname: str
    ip_address: Optional[str] = None
    server_type: Optional[str] = None
    os_family: str
    os_version: str
    region: Optional[str] = None
    dc: Optional[str] = None
    source: Optional[str] = None
    last_seen: datetime
    is_baseline: bool


class BaselineConfigCreate(BaseModel):
    server_type: str
    os_family: str
    os_version: Optional[str] = None
    region: Optional[str] = None
    parameter_definition_id: uuid.UUID
    expected_value: str
    is_critical: bool = False


class BaselineConfigOut(BaseModel):
    id: uuid.UUID
    server_type: str
    os_family: str
    os_version: Optional[str] = None
    region: Optional[str] = None
    parameter_definition_id: uuid.UUID
    expected_value: str
    is_critical: bool
    updated_at: datetime


class DriftFindingOut(BaseModel):
    id: uuid.UUID
    server_id: uuid.UUID
    parameter_definition_id: Optional[uuid.UUID] = None
    category: str
    parameter_key: str
    baseline_value: Optional[str] = None
    current_value: Optional[str] = None
    previous_value: Optional[str] = None
    drift_type: str
    severity: str


class DriftReportOut(BaseModel):
    id: uuid.UUID
    generated_at: datetime
    total_servers: int
    compliant_count: int
    critical_count: int
    warning_count: int
    unreachable_count: int
    source: Optional[str] = None


class RuleCreate(BaseModel):
    dc_name: str
    parameter_definition_id: uuid.UUID
    expected_value: str


class RuleOut(BaseModel):
    id: uuid.UUID
    dc_name: str
    parameter_definition_id: uuid.UUID
    expected_value: str
    created_at: datetime
    updated_at: datetime
