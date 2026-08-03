import os

os.environ["DB_URL"] = "postgresql+psycopg2://postgres:sentriq_test@localhost:5433/sentriq_test"
os.environ["EXCEL_OUTPUT_PATH"] = "/tmp/sentriq_test_output"
os.environ["CSV_OUTPUT_PATH"] = "/tmp/sentriq_test_output"

import pytest
from sqlalchemy import text

from app.db import engine
from app.models import Base


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables(_schema):
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE sq_schema.drift_findings, sq_schema.drift_reports, "
                "sq_schema.server_parameters, sq_schema.servers, sq_schema.rules, "
                "sq_schema.baseline_configs, sq_schema.parameter_definitions, "
                "sq_schema.excel_imports RESTART IDENTITY CASCADE"
            )
        )
    yield
