"""Smoke tests for SentriQ — verify imports and module loading."""


def test_app_imports():
    """The main app module should import without error."""
    from app.main import app
    assert app is not None


def test_models_import():
    """SQLAlchemy models should import without error."""
    from app import models
    assert models is not None


def test_schemas_import():
    """Pydantic schemas should import without error."""
    from app import schemas
    assert schemas is not None
