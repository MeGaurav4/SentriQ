import uuid
from typing import List, Optional
from sqlalchemy import select, delete, text
from app.db import get_session
from app.models import ParameterDefinition, Region, BaselineConfig, Server, ServerParameter, DriftReport, DriftFinding, Rule
from app.schemas import ParameterDefinitionCreate, ParameterDefinitionUpdate, RegionCreate, BaselineConfigCreate, RuleCreate


def list_parameters(os_family: Optional[str] = None) -> List[ParameterDefinition]:
    with get_session() as session:
        q = select(ParameterDefinition).order_by(ParameterDefinition.sort_order, ParameterDefinition.name)
        if os_family:
            q = q.where(ParameterDefinition.os_family == os_family.lower())
        return session.execute(q).scalars().all()


def get_parameter(param_id: uuid.UUID) -> Optional[ParameterDefinition]:
    with get_session() as session:
        return session.execute(
            select(ParameterDefinition).where(ParameterDefinition.id == param_id)
        ).scalar_one_or_none()


def create_parameter(data: ParameterDefinitionCreate) -> ParameterDefinition:
    with get_session() as session:
        param = ParameterDefinition(
            name=data.name,
            display_name=data.display_name,
            os_family=data.os_family,
            data_type=data.data_type,
            category=data.category,
            is_active=data.is_active,
            sort_order=data.sort_order,
            default_severity=data.default_severity,
            help_text=data.help_text,
        )
        session.add(param)
        session.commit()
        session.refresh(param)
        return param


def update_parameter(param_id: uuid.UUID, data: ParameterDefinitionUpdate) -> Optional[ParameterDefinition]:
    with get_session() as session:
        param = session.execute(
            select(ParameterDefinition).where(ParameterDefinition.id == param_id)
        ).scalar_one_or_none()
        if not param:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(param, key, value)
        session.commit()
        session.refresh(param)
        return param


def toggle_parameter(param_id: uuid.UUID) -> Optional[ParameterDefinition]:
    with get_session() as session:
        param = session.execute(
            select(ParameterDefinition).where(ParameterDefinition.id == param_id)
        ).scalar_one_or_none()
        if not param:
            return None
        param.is_active = not param.is_active
        session.commit()
        session.refresh(param)
        return param


def delete_all_parameters() -> int:
    with get_session() as session:
        session.execute(delete(DriftFinding))
        session.execute(delete(DriftReport))
        session.execute(delete(ServerParameter))
        session.execute(delete(Server))
        session.execute(
            text("UPDATE sq_schema.baseline_configs SET parameter_definition_id = NULL")
        )
        session.execute(
            text("UPDATE sq_schema.drift_findings SET parameter_definition_id = NULL")
        )
        count = session.execute(delete(ParameterDefinition)).rowcount
        session.commit()
        return count


def delete_parameter(param_id: uuid.UUID) -> bool:
    with get_session() as session:
        param = session.execute(
            select(ParameterDefinition).where(ParameterDefinition.id == param_id)
        ).scalar_one_or_none()
        if not param:
            return False
        session.delete(param)
        session.commit()
        return True


def list_regions() -> List[Region]:
    with get_session() as session:
        return session.execute(select(Region).order_by(Region.name)).scalars().all()


def create_region(data: RegionCreate) -> Region:
    with get_session() as session:
        region = Region(name=data.name, description=data.description)
        session.add(region)
        session.commit()
        session.refresh(region)
        return region


def list_baselines() -> List[BaselineConfig]:
    with get_session() as session:
        return session.execute(select(BaselineConfig).order_by(BaselineConfig.server_type, BaselineConfig.os_family, BaselineConfig.category, BaselineConfig.parameter_key)).scalars().all()


def get_baseline(baseline_id: uuid.UUID) -> Optional[BaselineConfig]:
    with get_session() as session:
        return session.execute(select(BaselineConfig).where(BaselineConfig.id == baseline_id)).scalar_one_or_none()


def create_baseline(data: BaselineConfigCreate) -> BaselineConfig:
    with get_session() as session:
        param_def = session.execute(
            select(ParameterDefinition).where(ParameterDefinition.id == data.parameter_definition_id)
        ).scalar_one_or_none()
        baseline = BaselineConfig(
            server_type=data.server_type,
            os_family=data.os_family,
            os_version=data.os_version,
            region=data.region,
            category=param_def.category if param_def else "system",
            parameter_key=param_def.name if param_def else "unknown",
            parameter_definition_id=data.parameter_definition_id,
            expected_value=data.expected_value,
            is_critical=data.is_critical,
        )
        session.add(baseline)
        session.commit()
        session.refresh(baseline)
        return baseline


def update_baseline(baseline_id: uuid.UUID, data: BaselineConfigCreate) -> Optional[BaselineConfig]:
    with get_session() as session:
        baseline = session.execute(select(BaselineConfig).where(BaselineConfig.id == baseline_id)).scalar_one_or_none()
        if not baseline:
            return None
        param_def = session.execute(
            select(ParameterDefinition).where(ParameterDefinition.id == data.parameter_definition_id)
        ).scalar_one_or_none()
        baseline.server_type = data.server_type
        baseline.os_family = data.os_family
        baseline.os_version = data.os_version
        baseline.region = data.region
        baseline.category = param_def.category if param_def else "system"
        baseline.parameter_key = param_def.name if param_def else "unknown"
        baseline.parameter_definition_id = data.parameter_definition_id
        baseline.expected_value = data.expected_value
        baseline.is_critical = data.is_critical
        session.commit()
        session.refresh(baseline)
        return baseline


def delete_all_baselines() -> int:
    with get_session() as session:
        session.execute(delete(DriftFinding))
        session.execute(delete(DriftReport))
        count = session.execute(delete(BaselineConfig)).rowcount
        session.commit()
        return count


def delete_baseline(baseline_id: uuid.UUID) -> bool:
    with get_session() as session:
        baseline = session.execute(select(BaselineConfig).where(BaselineConfig.id == baseline_id)).scalar_one_or_none()
        if not baseline:
            return False
        session.delete(baseline)
        session.commit()
        return True


def list_servers() -> List[Server]:
    with get_session() as session:
        return session.execute(select(Server).order_by(Server.hostname)).scalars().all()


def get_server_by_hostname(hostname: str) -> Optional[Server]:
    with get_session() as session:
        return session.execute(select(Server).where(Server.hostname == hostname.lower())).scalar_one_or_none()


def update_server_dc(hostname: str, dc: str) -> Optional[Server]:
    with get_session() as session:
        server = session.execute(
            select(Server).where(Server.hostname == hostname.lower())
        ).scalar_one_or_none()
        if not server:
            return None
        server.dc = dc or None
        session.commit()
        session.refresh(server)
        return server


def list_rules() -> List[Rule]:
    with get_session() as session:
        return session.execute(
            select(Rule).order_by(Rule.dc_name)
        ).scalars().all()


def get_rule(rule_id: uuid.UUID) -> Optional[Rule]:
    with get_session() as session:
        return session.execute(
            select(Rule).where(Rule.id == rule_id)
        ).scalar_one_or_none()


def create_rule(data: RuleCreate) -> Rule:
    with get_session() as session:
        rule = Rule(
            dc_name=data.dc_name,
            parameter_definition_id=data.parameter_definition_id,
            expected_value=data.expected_value,
        )
        session.add(rule)
        session.commit()
        session.refresh(rule)
        return rule


def update_rule(rule_id: uuid.UUID, data: RuleCreate) -> Optional[Rule]:
    with get_session() as session:
        rule = session.execute(
            select(Rule).where(Rule.id == rule_id)
        ).scalar_one_or_none()
        if not rule:
            return None
        rule.dc_name = data.dc_name
        rule.parameter_definition_id = data.parameter_definition_id
        rule.expected_value = data.expected_value
        session.commit()
        session.refresh(rule)
        return rule


def delete_rule(rule_id: uuid.UUID) -> bool:
    with get_session() as session:
        rule = session.execute(
            select(Rule).where(Rule.id == rule_id)
        ).scalar_one_or_none()
        if not rule:
            return False
        session.delete(rule)
        session.commit()
        return True


def delete_all_rules() -> int:
    with get_session() as session:
        count = session.execute(delete(Rule)).rowcount
        session.commit()
        return count
