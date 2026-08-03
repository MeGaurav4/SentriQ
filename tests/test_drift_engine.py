from datetime import datetime, timezone

from sqlalchemy import select

from app.db import get_session
from app.drift_engine import run_curated_drift_detection
from app.models import (
    BaselineConfig,
    DriftFinding,
    DriftReport,
    ParameterDefinition,
    Rule,
    Server,
    ServerParameter,
)


def add(session, obj):
    session.add(obj)
    session.flush()
    return obj


def make_server(
    session,
    hostname="web-01",
    ip_address="10.0.0.1",
    server_type="web",
    os_family="ubuntu",
    os_version="22.04",
    region="us-east",
    dc="dc1",
    source="test",
):
    return add(
        session,
        Server(
            hostname=hostname,
            ip_address=ip_address,
            server_type=server_type,
            os_family=os_family,
            os_version=os_version,
            region=region,
            dc=dc,
            source=source,
            last_seen=datetime.now(timezone.utc),
        ),
    )


def make_param_def(session, name="kernel.sysrq", category="os", data_type="string", is_active=True, os_family="ubuntu"):
    return add(
        session,
        ParameterDefinition(
            name=name,
            display_name=name,
            os_family=os_family,
            data_type=data_type,
            category=category,
            is_active=is_active,
        ),
    )


def make_baseline(
    session,
    param_def,
    expected_value="1",
    server_type="web",
    os_family="ubuntu",
    category="os",
    is_critical=False,
):
    return add(
        session,
        BaselineConfig(
            server_type=server_type,
            os_family=os_family,
            category=category,
            parameter_key=param_def.name,
            parameter_definition_id=param_def.id,
            expected_value=expected_value,
            is_critical=is_critical,
        ),
    )


def make_rule(session, param_def, expected_value, dc_name="dc1"):
    return add(
        session,
        Rule(
            dc_name=dc_name,
            parameter_definition_id=param_def.id,
            expected_value=expected_value,
        ),
    )


def make_server_param(session, server, param_def, value, collected_at=None):
    return add(
        session,
        ServerParameter(
            server_id=server.id,
            parameter_definition_id=param_def.id,
            parameter_value=value,
            collected_at=collected_at or datetime.now(timezone.utc),
            source="test",
        ),
    )


def run_and_fetch():
    session = get_session()
    try:
        report_id = run_curated_drift_detection()
        session.expire_all()
        report = session.get(DriftReport, report_id)
        findings = session.execute(
            select(DriftFinding).where(DriftFinding.report_id == report_id)
        ).scalars().all()
        return report, findings
    finally:
        session.close()


def test_empty_fleet_creates_zero_report():
    report, findings = run_and_fetch()
    assert report.total_servers == 0
    assert report.compliant_count == 0
    assert report.unreachable_count == 0
    assert report.source == "curated"
    assert findings == []


def test_compliant_server_produces_no_findings():
    session = get_session()
    try:
        server = make_server(session)
        param_def = make_param_def(session)
        make_baseline(session, param_def, expected_value="1")
        make_server_param(session, server, param_def, "1")
        session.commit()

        report, findings = run_and_fetch()
        assert report.total_servers == 1
        assert report.compliant_count == 1
        assert report.critical_count == 0
        assert report.warning_count == 0
        assert findings == []
    finally:
        session.close()


def test_baseline_mismatch_non_critical_is_warning():
    session = get_session()
    try:
        server = make_server(session)
        param_def = make_param_def(session)
        make_baseline(session, param_def, expected_value="1", is_critical=False)
        make_server_param(session, server, param_def, "0")
        session.commit()

        report, findings = run_and_fetch()
        assert report.compliant_count == 0
        assert report.warning_count == 1
        assert len(findings) == 1
        f = findings[0]
        assert f.drift_type == "vs_baseline"
        assert f.severity == "warning"
        assert f.baseline_value == "1"
        assert f.current_value == "0"
    finally:
        session.close()


def test_baseline_mismatch_critical_is_critical():
    session = get_session()
    try:
        server = make_server(session)
        param_def = make_param_def(session)
        make_baseline(session, param_def, expected_value="1", is_critical=True)
        make_server_param(session, server, param_def, "0")
        session.commit()

        report, findings = run_and_fetch()
        assert report.compliant_count == 0
        assert report.critical_count == 1
        assert len(findings) == 1
        f = findings[0]
        assert f.drift_type == "vs_baseline"
        assert f.severity == "critical"
    finally:
        session.close()


def test_missing_baseline_key_reported_as_key_not_present():
    session = get_session()
    try:
        server = make_server(session)
        baseline_param = make_param_def(session, name="kernel.sysrq")
        other_param = make_param_def(session, name="kernel.shmmax")
        make_baseline(session, baseline_param, expected_value="1")
        # server is reachable (has data) but missing the baseline param
        make_server_param(session, server, other_param, "4294967296")
        session.commit()

        report, findings = run_and_fetch()
        assert report.compliant_count == 0
        assert report.unreachable_count == 0
        missing = [f for f in findings if f.current_value == "KEY_NOT_PRESENT"]
        assert len(missing) == 1
        f = missing[0]
        assert f.parameter_definition_id == baseline_param.id
        assert f.drift_type == "vs_baseline"
        assert f.severity == "info"
    finally:
        session.close()


def test_unlisted_parameter_reported_as_not_in_baseline():
    session = get_session()
    try:
        server = make_server(session)
        param_def = make_param_def(session, name="kernel.shmmax")
        make_server_param(session, server, param_def, "4294967296")
        session.commit()

        report, findings = run_and_fetch()
        # server is still counted compliant: NOT_IN_BASELINE is info-only
        assert report.compliant_count == 1
        assert len(findings) == 1
        f = findings[0]
        assert f.drift_type == "vs_baseline"
        assert f.severity == "info"
        assert f.baseline_value == "NOT_IN_BASELINE"
    finally:
        session.close()


def test_previous_value_change_is_warning():
    session = get_session()
    try:
        server = make_server(session)
        param_def = make_param_def(session, name="kernel.sysrq")
        # baseline matches the current value, so only the change is flagged
        make_baseline(session, param_def, expected_value="1")
        make_server_param(session, server, param_def, "0", collected_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
        make_server_param(session, server, param_def, "1", collected_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
        session.commit()

        report, findings = run_and_fetch()
        # vs_previous findings are warning severity but do not flip compliance
        assert report.compliant_count == 1
        assert report.warning_count == 1
        assert len(findings) == 1
        f = findings[0]
        assert f.drift_type == "vs_previous"
        assert f.severity == "warning"
        assert f.previous_value == "0"
        assert f.current_value == "1"
    finally:
        session.close()


def test_previous_key_removed_branch_is_unreachable():
    # The vs_previous window partitions by (server_id, parameter_definition_id),
    # so a param with rn==2 (previous) always also has rn==1 (current).
    # KEY_REMOVED can therefore never fire with the current query.
    session = get_session()
    try:
        server = make_server(session)
        param_def = make_param_def(session, name="kernel.sysrq")
        make_baseline(session, param_def, expected_value="0")
        make_server_param(session, server, param_def, "0", collected_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
        make_server_param(session, server, param_def, "0", collected_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
        session.commit()

        report, findings = run_and_fetch()
        assert report.compliant_count == 1
        assert findings == []
    finally:
        session.close()


def test_rule_overrides_baseline_expected_value():
    session = get_session()
    try:
        server = make_server(session)
        param_def = make_param_def(session)
        make_baseline(session, param_def, expected_value="1")
        make_rule(session, param_def, expected_value="5")
        make_server_param(session, server, param_def, "1")
        session.commit()

        report, findings = run_and_fetch()
        # rule expects 5, server has 1, so this is now a finding
        assert report.compliant_count == 0
        assert len(findings) == 1
        f = findings[0]
        assert f.drift_type == "vs_baseline"
        assert f.baseline_value == "5"
        assert f.current_value == "1"
    finally:
        session.close()


def test_server_without_data_is_unreachable():
    session = get_session()
    try:
        make_server(session, hostname="web-02")
        session.commit()

        report, findings = run_and_fetch()
        assert report.total_servers == 1
        assert report.unreachable_count == 1
        assert report.compliant_count == 0
        assert findings == []
    finally:
        session.close()


def test_mixed_fleet_counts():
    session = get_session()
    try:
        # compliant server (type web/ubuntu, baseline for its type)
        s1 = make_server(session, hostname="web-01", server_type="web", os_family="ubuntu")
        p1 = make_param_def(session, name="kernel.sysrq", os_family="ubuntu")
        make_baseline(session, p1, expected_value="1", server_type="web", os_family="ubuntu")
        make_server_param(session, s1, p1, "1")

        # critical drift server (different type, own baseline)
        s2 = make_server(session, hostname="db-01", server_type="db", os_family="ubuntu")
        p2 = make_param_def(session, name="net.ipv4.ip_forward", os_family="ubuntu")
        make_baseline(session, p2, expected_value="0", server_type="db", os_family="ubuntu", is_critical=True)
        make_server_param(session, s2, p2, "1")

        # unreachable server
        make_server(session, hostname="cache-01", server_type="cache", os_family="ubuntu")

        session.commit()

        report, findings = run_and_fetch()
        assert report.total_servers == 3
        assert report.compliant_count == 1
        assert report.critical_count == 1
        assert report.warning_count == 0
        assert report.unreachable_count == 1
        assert len(findings) == 1
    finally:
        session.close()
