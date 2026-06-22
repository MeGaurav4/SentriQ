"""initial schema for SentriQ

Revision ID: a64a61debd6e
Revises:
Create Date: 2026-06-20 12:57:54.682416

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models import Base


revision: str = 'a64a61debd6e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS sq_schema')
    Base.metadata.create_all(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind(), checkfirst=True)
    op.execute('DROP SCHEMA IF EXISTS sq_schema CASCADE')
