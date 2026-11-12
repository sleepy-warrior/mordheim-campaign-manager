"""create campaigns and campaign members

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visibility", sa.String(length=20), server_default=sa.text("'private'"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("rules_mode", sa.String(length=20), server_default=sa.text("'standard'"), nullable=False),
        sa.Column("max_bands_per_player", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("starting_gold", sa.Integer(), server_default=sa.text("500"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("visibility IN ('public', 'private')", name="ck_campaigns_visibility"),
        sa.CheckConstraint("status IN ('draft', 'active', 'completed', 'archived')", name="ck_campaigns_status"),
        sa.CheckConstraint("rules_mode IN ('standard', 'free')", name="ck_campaigns_rules_mode"),
        sa.CheckConstraint("max_bands_per_player > 0", name="ck_campaigns_max_bands_positive"),
        sa.CheckConstraint("starting_gold >= 0", name="ck_campaigns_starting_gold_nonnegative"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaigns_creator_id", "campaigns", ["creator_id"])

    op.create_table(
        "campaign_members",
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), server_default=sa.text("'player'"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('master', 'player')", name="ck_campaign_members_role"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("campaign_id", "user_id"),
    )
    op.create_index(
        "uq_campaign_members_one_master",
        "campaign_members",
        ["campaign_id"],
        unique=True,
        postgresql_where=sa.text("role = 'master'"),
    )


def downgrade() -> None:
    op.drop_index("uq_campaign_members_one_master", table_name="campaign_members")
    op.drop_table("campaign_members")
    op.drop_index("ix_campaigns_creator_id", table_name="campaigns")
    op.drop_table("campaigns")
