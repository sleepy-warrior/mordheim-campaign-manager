"""make user email uniqueness case-insensitive

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize existing values without deleting rows. If normalization creates
    # duplicates, PostgreSQL aborts the migration and leaves the transaction intact.
    op.execute(sa.text("UPDATE users SET email = lower(email)"))
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.create_index(
        "uq_users_email",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_users_email", table_name="users")
    op.create_unique_constraint("uq_users_email", "users", ["email"])
