"""add cancelled to scanstatus enum

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-07 00:00:00.000000

"""
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE ... ADD VALUE outside of a transaction block
    op.execute("ALTER TYPE scanstatus ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    # To downgrade, recreate the type without 'cancelled' and cast the column.
    op.execute("""
        DELETE FROM scans WHERE status = 'cancelled'
    """)
    op.execute("""
        ALTER TABLE scans
            ALTER COLUMN status TYPE VARCHAR(32)
    """)
    op.execute("DROP TYPE scanstatus")
    op.execute("""
        CREATE TYPE scanstatus AS ENUM ('pending', 'running', 'paused', 'finished', 'failed')
    """)
    op.execute("""
        ALTER TABLE scans
            ALTER COLUMN status TYPE scanstatus USING status::scanstatus
    """)
