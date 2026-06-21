import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Text, func, Integer, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    __table_args__ = {"schema": "sq_schema"}


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    hostname: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    server_type: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    os_family: Mapped[str] = mapped_column(String(50), index=True)
    os_version: Mapped[str] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(100))
    dc: Mapped[Optional[str]] = mapped_column(String(100))
    source: Mapped[Optional[str]] = mapped_column(String(50))
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)

    curated_parameters: Mapped[List["ServerParameter"]] = relationship(
        back_populates="server", cascade="all, delete-orphan"
    )


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dc_name: Mapped[str] = mapped_column(String(100), index=True)
    parameter_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sq_schema.parameter_definitions.id")
    )
    expected_value: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_rule_dc_param", "dc_name", "parameter_definition_id", unique=True),
        {"schema": "sq_schema"},
    )


class BaselineConfig(Base):
    __tablename__ = "baseline_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    server_type: Mapped[str] = mapped_column(String(50), index=True)
    os_family: Mapped[str] = mapped_column(String(50), index=True)
    os_version: Mapped[Optional[str]] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(100))
    parameter_key: Mapped[str] = mapped_column(String(500))
    parameter_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sq_schema.parameter_definitions.id")
    )
    expected_value: Mapped[str] = mapped_column(Text)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DriftReport(Base):
    __tablename__ = "drift_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    total_servers: Mapped[int] = mapped_column()
    compliant_count: Mapped[int] = mapped_column()
    critical_count: Mapped[int] = mapped_column()
    warning_count: Mapped[int] = mapped_column()
    unreachable_count: Mapped[int] = mapped_column()
    source: Mapped[Optional[str]] = mapped_column(String(50))

    findings: Mapped[List["DriftFinding"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class DriftFinding(Base):
    __tablename__ = "drift_findings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sq_schema.drift_reports.id"), index=True
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sq_schema.servers.id"), index=True
    )
    category: Mapped[str] = mapped_column(String(100))
    parameter_key: Mapped[str] = mapped_column(String(500))
    parameter_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sq_schema.parameter_definitions.id")
    )
    baseline_value: Mapped[Optional[str]] = mapped_column(Text)
    current_value: Mapped[Optional[str]] = mapped_column(Text)
    previous_value: Mapped[Optional[str]] = mapped_column(Text)
    drift_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(50), index=True)
    first_detected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    report: Mapped["DriftReport"] = relationship(back_populates="findings")

    __table_args__ = (
        Index("ix_report_server_severity", "report_id", "server_id", "severity"),
        {"schema": "sq_schema"},
    )


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)


class ParameterDefinition(Base):
    __tablename__ = "parameter_definitions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    os_family: Mapped[str] = mapped_column(String(50))
    data_type: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    default_severity: Mapped[str] = mapped_column(String(20), default="warning")
    help_text: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("ix_param_name_os", "name", "os_family", unique=True),
        {"schema": "sq_schema"},
    )


class ServerParameter(Base):
    __tablename__ = "server_parameters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sq_schema.servers.id"), index=True
    )
    parameter_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sq_schema.parameter_definitions.id"), index=True
    )
    parameter_value: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(50))

    server: Mapped["Server"] = relationship(back_populates="curated_parameters")

    __table_args__ = (
        Index("ix_server_param_lookup", "server_id", "parameter_definition_id", "collected_at"),
        {"schema": "sq_schema"},
    )


class ExcelImport(Base):
    __tablename__ = "excel_imports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(500))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[Optional[str]] = mapped_column(Text)
