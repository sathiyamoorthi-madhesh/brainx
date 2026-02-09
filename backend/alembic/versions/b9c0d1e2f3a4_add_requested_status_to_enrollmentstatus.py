"""Add requested status to enrollmentstatus enum

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-02-09 01:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b9c0d1e2f3a4'
down_revision = 'a8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade():
    # Add 'requested' value to enrollmentstatus enum
    # PostgreSQL requires ALTER TYPE to add new enum values
    op.execute("ALTER TYPE enrollmentstatus ADD VALUE IF NOT EXISTS 'requested' BEFORE 'active'")


def downgrade():
    # Note: PostgreSQL does not support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For safety, we leave the enum value in place
    pass
