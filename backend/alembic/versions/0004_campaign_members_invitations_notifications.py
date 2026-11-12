"""add campaign membership workflow and notifications

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("max_members", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_campaigns_max_members_positive",
        "campaigns",
        "max_members IS NULL OR max_members > 0",
    )

    op.add_column("campaign_members", sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False))
    op.add_column("campaign_members", sa.Column("left_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaign_members", sa.Column("excluded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaign_members", sa.Column("exclusion_reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_campaign_members_status",
        "campaign_members",
        "status IN ('active', 'left', 'excluded')",
    )
    op.drop_index("uq_campaign_members_one_master", table_name="campaign_members")
    op.create_index(
        "uq_campaign_members_one_active_master",
        "campaign_members",
        ["campaign_id"],
        unique=True,
        postgresql_where=sa.text("role = 'master' AND status = 'active'"),
    )

    op.create_table(
        "campaign_join_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "uq_campaign_join_links_active_campaign",
        "campaign_join_links",
        ["campaign_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "campaign_join_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("join_link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_campaign_join_requests_status"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["join_link_id"], ["campaign_join_links.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_campaign_join_requests_pending_user", "campaign_join_requests", ["campaign_id", "user_id"], unique=True, postgresql_where=sa.text("status = 'pending'"))

    op.create_table(
        "campaign_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'declined', 'revoked')", name="ck_campaign_invitations_status"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_campaign_invitations_pending_user", "campaign_invitations", ["campaign_id", "user_id"], unique=True, postgresql_where=sa.text("status = 'pending'"))

    op.create_table(
        "campaign_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("details", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_recipient_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("campaign_events")
    op.drop_index("uq_campaign_invitations_pending_user", table_name="campaign_invitations")
    op.drop_table("campaign_invitations")
    op.drop_index("uq_campaign_join_requests_pending_user", table_name="campaign_join_requests")
    op.drop_table("campaign_join_requests")
    op.drop_index("uq_campaign_join_links_active_campaign", table_name="campaign_join_links")
    op.drop_table("campaign_join_links")
    op.drop_index("uq_campaign_members_one_active_master", table_name="campaign_members")
    op.create_index("uq_campaign_members_one_master", "campaign_members", ["campaign_id"], unique=True, postgresql_where=sa.text("role = 'master'"))
    op.drop_constraint("ck_campaign_members_status", "campaign_members", type_="check")
    op.drop_column("campaign_members", "exclusion_reason")
    op.drop_column("campaign_members", "excluded_at")
    op.drop_column("campaign_members", "left_at")
    op.drop_column("campaign_members", "status")
    op.drop_constraint("ck_campaigns_max_members_positive", "campaigns", type_="check")
    op.drop_column("campaigns", "max_members")
