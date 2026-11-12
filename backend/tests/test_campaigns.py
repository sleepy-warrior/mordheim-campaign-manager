import os
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")

from app.main import app
from app.models import Campaign, CampaignMember, User
from app.models import CampaignEvent, CampaignJoinLink, CampaignInvitation, Notification
from app.modules.campaigns.schemas import CampaignCreate, CampaignRole, CampaignStatusUpdate, CampaignUpdate
from app.modules.campaigns.service import (
    CampaignAccessDeniedError,
    CampaignNotFoundError,
    create_campaign,
    get_campaign,
    update_campaign,
    update_campaign_status,
)
from app.modules.campaigns.workflow_service import WorkflowError, transfer_master


def make_user() -> User:
    now = datetime.now(timezone.utc)
    return User(id=uuid.uuid4(), email="player@example.com", username="player", password_hash="hash", created_at=now, updated_at=now)


class FakeSession:
    def __init__(self, campaign: Campaign | None = None):
        self.campaign = campaign
        self.added: Any = None
        self.rollback_called = False

    def scalar(self, statement: Any) -> Campaign | None:
        return self.campaign

    def add(self, value: Any) -> None:
        self.added = value

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        self.rollback_called = True

    def refresh(self, value: Any) -> None:
        now = datetime.now(timezone.utc)
        value.id = value.id or uuid.uuid4()
        value.created_at = value.created_at or now
        value.updated_at = now


class TransferSession:
    def __init__(self, values: list[Any], fail_on_flush: bool = False, fail_on_commit: bool = False):
        self.values = iter(values)
        self.added_items: list[Any] = []
        self.rollback_called = False
        self.fail_on_flush = fail_on_flush
        self.fail_on_commit = fail_on_commit

    def scalar(self, statement: Any) -> Any:
        return next(self.values)

    def add(self, value: Any) -> None:
        self.added_items.append(value)

    def flush(self) -> None:
        if self.fail_on_flush:
            raise RuntimeError("flush failed")

    def commit(self) -> None:
        if self.fail_on_commit:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        self.rollback_called = True


def make_campaign(master: User, player: User | None = None) -> Campaign:
    campaign = Campaign(id=uuid.uuid4(), name="Ruins", creator_id=master.id, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    campaign.members.append(CampaignMember(user_id=master.id, role=CampaignRole.MASTER.value, user=master))
    if player:
        campaign.members.append(CampaignMember(user_id=player.id, role=CampaignRole.PLAYER.value, user=player))
    return campaign


def test_create_campaign_assigns_creator_as_master() -> None:
    creator = make_user()
    session = FakeSession()
    campaign = create_campaign(session, creator, CampaignCreate(name="Ruins"))

    assert campaign.creator_id == creator.id
    assert len(campaign.members) == 1
    assert campaign.members[0].user_id == creator.id
    assert campaign.members[0].role == "master"


def test_master_can_update_settings_and_status() -> None:
    master = make_user()
    campaign = make_campaign(master)
    session = FakeSession(campaign)

    updated = update_campaign(
        session,
        campaign.id,
        master.id,
        CampaignUpdate(
            name="New Ruins",
            description="A harsher campaign",
            visibility="public",
            rules_mode="free",
            max_bands_per_player=3,
            starting_gold=750,
        ),
    )
    assert updated.name == "New Ruins"
    assert updated.description == "A harsher campaign"
    assert updated.visibility == "public"
    assert updated.rules_mode == "free"
    assert updated.max_bands_per_player == 3
    assert updated.starting_gold == 750

    updated = update_campaign_status(session, campaign.id, master.id, CampaignStatusUpdate(status="active"))
    assert updated.status == "active"


def test_player_can_read_but_cannot_update_campaign() -> None:
    master = make_user()
    player = make_user()
    campaign = make_campaign(master, player)
    session = FakeSession(campaign)

    visible, membership = get_campaign(session, campaign.id, player.id)
    assert visible is campaign
    assert membership is not None and membership.role == "player"
    with pytest.raises(CampaignAccessDeniedError):
        update_campaign(session, campaign.id, player.id, CampaignUpdate(name="Nope"))


def test_private_campaign_hides_from_non_member_and_public_campaign_is_readable() -> None:
    master = make_user()
    outsider = make_user()
    campaign = make_campaign(master)
    session = FakeSession(campaign)

    with pytest.raises(CampaignNotFoundError):
        get_campaign(session, campaign.id, outsider.id)

    campaign.visibility = "public"
    visible, membership = get_campaign(session, campaign.id, outsider.id)
    assert visible is campaign
    assert membership is None

    with pytest.raises(CampaignNotFoundError):
        update_campaign(session, campaign.id, outsider.id, CampaignUpdate(name="Nope"))


def test_campaign_member_primary_key_prevents_duplicate_members() -> None:
    table = CampaignMember.__table__
    assert {column.name for column in table.primary_key.columns} == {"campaign_id", "user_id"}
    assert not any(constraint.name == "uq_campaign_members_campaign_user" for constraint in table.constraints)


def test_campaign_workflow_models_keep_token_hashes_and_event_history() -> None:
    assert CampaignJoinLink.__table__.c.token_hash.type.length == 64
    assert CampaignEvent.__table__.c.event_type.type.length == 50
    assert "details" in CampaignEvent.__table__.c
    assert Notification.__table__.c.metadata is not None
    assert any(index.name == "uq_campaign_invitations_pending_user" for index in CampaignInvitation.__table__.indexes)


def test_transfer_master_changes_roles_once_and_notifies_only_both_masters() -> None:
    master, player = make_user(), make_user()
    campaign = make_campaign(master, player)
    current, replacement = campaign.members
    current.status = replacement.status = "active"
    session = TransferSession([campaign, current, current, replacement])

    transfer_master(session, master.id, campaign.id, player.id)

    assert current.role == "player" and replacement.role == "master"
    assert sum(member.role == "master" and member.status == "active" for member in campaign.members) == 1
    assert len([item for item in session.added_items if isinstance(item, CampaignEvent)]) == 1
    notifications = [item for item in session.added_items if isinstance(item, Notification)]
    assert {item.recipient_id for item in notifications} == {master.id, player.id}
    assert len(notifications) == 2


def test_transfer_master_rejects_player_and_former_member() -> None:
    master, player = make_user(), make_user()
    campaign = make_campaign(master, player)
    campaign.members[0].status = "active"
    campaign.members[1].status = "active"
    player_session = TransferSession([campaign, campaign.members[1]])
    with pytest.raises(WorkflowError) as player_error:
        transfer_master(player_session, player.id, campaign.id, master.id)
    assert player_error.value.code == "forbidden"
    assert player_session.rollback_called

    former_session = TransferSession([campaign, campaign.members[0], campaign.members[0], None])
    with pytest.raises(WorkflowError) as former_error:
        transfer_master(former_session, master.id, campaign.id, player.id)
    assert former_error.value.code == "not_found"
    assert former_session.rollback_called


def test_transfer_master_rolls_back_when_flush_fails() -> None:
    master, player = make_user(), make_user()
    campaign = make_campaign(master, player)
    current, replacement = campaign.members
    current.status = replacement.status = "active"
    session = TransferSession([campaign, current, current, replacement], fail_on_flush=True)

    with pytest.raises(RuntimeError, match="flush failed"):
        transfer_master(session, master.id, campaign.id, player.id)
    assert session.rollback_called


def test_patch_preflight_allows_authorization_header() -> None:
    response = TestClient(app).options(
        "/api/v1/campaigns/00000000-0000-0000-0000-000000000000",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
