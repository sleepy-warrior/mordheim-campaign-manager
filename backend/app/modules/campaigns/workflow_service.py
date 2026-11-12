import hashlib
import os
import secrets
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Campaign,
    CampaignEvent,
    CampaignInvitation,
    CampaignJoinLink,
    CampaignJoinRequest,
    CampaignMember,
    User,
)
from app.modules.notifications.service import create_notification

from .schemas import CampaignRole


class WorkflowError(Exception):
    def __init__(self, message: str, code: str = "conflict") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _campaign_for_update(db: Session, campaign_id: UUID) -> Campaign:
    campaign = db.scalar(select(Campaign).where(Campaign.id == campaign_id).with_for_update())
    if campaign is None:
        raise WorkflowError("Campaign not found", "not_found")
    return campaign


def _active_member(db: Session, campaign_id: UUID, user_id: UUID) -> CampaignMember | None:
    return db.scalar(select(CampaignMember).where(CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == user_id, CampaignMember.status == "active").with_for_update())


def _master(db: Session, campaign_id: UUID) -> CampaignMember:
    member = db.scalar(select(CampaignMember).where(CampaignMember.campaign_id == campaign_id, CampaignMember.role == "master", CampaignMember.status == "active"))
    if member is None:
        raise WorkflowError("Campaign master not found", "not_found")
    return member


def _require_master(db: Session, campaign_id: UUID, user_id: UUID) -> Campaign:
    campaign = _campaign_for_update(db, campaign_id)
    member = _active_member(db, campaign_id, user_id)
    if member is None or member.role != CampaignRole.MASTER.value:
        raise WorkflowError("Only the campaign master can perform this action", "forbidden")
    return campaign


def _check_capacity(db: Session, campaign: Campaign) -> None:
    if campaign.status == "archived":
        raise WorkflowError("Archived campaigns do not accept new members")
    if campaign.max_members is None:
        return
    active_count = db.scalar(select(func.count()).select_from(CampaignMember).where(CampaignMember.campaign_id == campaign.id, CampaignMember.status == "active")) or 0
    if active_count >= campaign.max_members:
        raise WorkflowError("Campaign member limit has been reached", "limit")


def _event(db: Session, campaign_id: UUID, author_id: UUID | None, event_type: str, details: dict[str, object]) -> None:
    db.add(CampaignEvent(campaign_id=campaign_id, author_id=author_id, event_type=event_type, details=details))


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_join_link(db: Session, master_id: UUID, campaign_id: UUID) -> tuple[CampaignJoinLink, str]:
    campaign = _require_master(db, campaign_id, master_id)
    existing = db.scalar(select(CampaignJoinLink).where(CampaignJoinLink.campaign_id == campaign_id, CampaignJoinLink.revoked_at.is_(None)))
    if existing is not None:
        raise WorkflowError("An active join link already exists")
    token = secrets.token_urlsafe(32)
    link = CampaignJoinLink(campaign_id=campaign_id, created_by=master_id, token_hash=_token_hash(token))
    db.add(link)
    _event(db, campaign_id, master_id, "join_link_created", {})
    _commit(db)
    db.refresh(link)
    return link, token


def revoke_join_link(db: Session, master_id: UUID, campaign_id: UUID) -> None:
    _require_master(db, campaign_id, master_id)
    link = db.scalar(select(CampaignJoinLink).where(CampaignJoinLink.campaign_id == campaign_id, CampaignJoinLink.revoked_at.is_(None)).with_for_update())
    if link is None:
        raise WorkflowError("Active join link not found", "not_found")
    link.revoked_at = _now()
    _event(db, campaign_id, master_id, "join_link_revoked", {})
    _commit(db)


def apply_join_request(db: Session, user_id: UUID, token: str) -> CampaignJoinRequest:
    link = db.scalar(select(CampaignJoinLink).where(CampaignJoinLink.token_hash == _token_hash(token), CampaignJoinLink.revoked_at.is_(None)))
    if link is None:
        raise WorkflowError("Join link is invalid or revoked", "not_found")
    campaign = _campaign_for_update(db, link.campaign_id)
    if _active_member(db, campaign.id, user_id) is not None:
        raise WorkflowError("You are already a member of this campaign")
    pending = db.scalar(select(CampaignJoinRequest).where(CampaignJoinRequest.campaign_id == campaign.id, CampaignJoinRequest.user_id == user_id, CampaignJoinRequest.status == "pending"))
    if pending is not None:
        raise WorkflowError("You already have a pending join request")
    request = CampaignJoinRequest(campaign_id=campaign.id, user_id=user_id, join_link_id=link.id)
    db.add(request)
    master = _master(db, campaign.id)
    _event(db, campaign.id, user_id, "join_request_created", {"user_id": str(user_id)})
    create_notification(db, recipient_id=master.user_id, actor_id=user_id, campaign_id=campaign.id, notification_type="join_request", title="Новая заявка", message=f"Пользователь подал заявку в кампанию «{campaign.name}»." )
    _commit(db)
    db.refresh(request)
    return request


def _membership_for_reactivation(db: Session, campaign_id: UUID, user_id: UUID) -> CampaignMember | None:
    return db.scalar(select(CampaignMember).where(CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == user_id).with_for_update())


def _activate_membership(db: Session, campaign: Campaign, user_id: UUID, role: str = "player") -> CampaignMember:
    _check_capacity(db, campaign)
    member = _membership_for_reactivation(db, campaign.id, user_id)
    now = _now()
    if member is None:
        member = CampaignMember(campaign_id=campaign.id, user_id=user_id, role=role, status="active", joined_at=now)
        db.add(member)
    else:
        member.status = "active"
        member.role = role
        member.joined_at = now
        member.left_at = None
        member.excluded_at = None
        member.exclusion_reason = None
    return member


def review_join_request(db: Session, master_id: UUID, request_id: UUID, approve: bool) -> CampaignJoinRequest:
    request = db.scalar(select(CampaignJoinRequest).where(CampaignJoinRequest.id == request_id).with_for_update())
    if request is None:
        raise WorkflowError("Join request not found", "not_found")
    campaign = _require_master(db, request.campaign_id, master_id)
    if request.status != "pending":
        raise WorkflowError("Join request is no longer pending")
    request.status = "approved" if approve else "rejected"
    request.reviewed_by = master_id
    request.reviewed_at = _now()
    if approve:
        _activate_membership(db, campaign, request.user_id)
        message = f"Ваша заявка в кампанию «{campaign.name}» одобрена."
        event_type = "join_request_approved"
    else:
        message = f"Ваша заявка в кампанию «{campaign.name}» отклонена."
        event_type = "join_request_rejected"
    _event(db, campaign.id, master_id, event_type, {"user_id": str(request.user_id)})
    create_notification(db, recipient_id=request.user_id, actor_id=master_id, campaign_id=campaign.id, notification_type=event_type, title="Заявка обработана", message=message)
    _commit(db)
    return request


def invite_user(db: Session, master_id: UUID, campaign_id: UUID, user: User) -> CampaignInvitation:
    campaign = _require_master(db, campaign_id, master_id)
    if user.id == master_id:
        raise WorkflowError("You cannot invite yourself")
    if _active_member(db, campaign_id, user.id) is not None:
        raise WorkflowError("User is already a campaign member")
    existing = db.scalar(select(CampaignInvitation).where(CampaignInvitation.campaign_id == campaign_id, CampaignInvitation.user_id == user.id, CampaignInvitation.status == "pending"))
    if existing is not None:
        raise WorkflowError("An active invitation already exists")
    invitation = CampaignInvitation(campaign_id=campaign_id, user_id=user.id, invited_by=master_id)
    db.add(invitation)
    _event(db, campaign_id, master_id, "invitation_created", {"user_id": str(user.id)})
    create_notification(db, recipient_id=user.id, actor_id=master_id, campaign_id=campaign_id, notification_type="invitation", title="Приглашение в кампанию", message=f"Вас пригласили в кампанию «{campaign.name}»." )
    _commit(db)
    db.refresh(invitation)
    return invitation


def respond_invitation(db: Session, user_id: UUID, invitation_id: UUID, accept: bool) -> CampaignInvitation:
    invitation = db.scalar(select(CampaignInvitation).where(CampaignInvitation.id == invitation_id, CampaignInvitation.user_id == user_id).with_for_update())
    if invitation is None:
        raise WorkflowError("Invitation not found", "not_found")
    if invitation.status != "pending":
        raise WorkflowError("Invitation is no longer pending")
    campaign = _campaign_for_update(db, invitation.campaign_id)
    invitation.status = "accepted" if accept else "declined"
    invitation.responded_at = _now()
    if accept:
        _activate_membership(db, campaign, user_id)
        event_type = "invitation_accepted"
        message = f"Пользователь принял приглашение в «{campaign.name}»."
    else:
        event_type = "invitation_declined"
        message = f"Пользователь отклонил приглашение в «{campaign.name}»."
    _event(db, campaign.id, user_id, event_type, {"user_id": str(user_id)})
    create_notification(db, recipient_id=invitation.invited_by, actor_id=user_id, campaign_id=campaign.id, notification_type=event_type, title="Ответ на приглашение", message=message)
    _commit(db)
    return invitation


def revoke_invitation(db: Session, master_id: UUID, invitation_id: UUID) -> CampaignInvitation:
    invitation = db.scalar(select(CampaignInvitation).where(CampaignInvitation.id == invitation_id).with_for_update())
    if invitation is None:
        raise WorkflowError("Invitation not found", "not_found")
    campaign = _require_master(db, invitation.campaign_id, master_id)
    if invitation.status != "pending":
        raise WorkflowError("Invitation is no longer pending")
    invitation.status = "revoked"
    invitation.revoked_at = _now()
    _event(db, campaign.id, master_id, "invitation_revoked", {"user_id": str(invitation.user_id)})
    create_notification(db, recipient_id=invitation.user_id, actor_id=master_id, campaign_id=campaign.id, notification_type="invitation_revoked", title="Приглашение отозвано", message=f"Приглашение в кампанию «{campaign.name}» отозвано.")
    _commit(db)
    return invitation


def leave_campaign(db: Session, user_id: UUID, campaign_id: UUID) -> CampaignMember:
    campaign = _campaign_for_update(db, campaign_id)
    member = _active_member(db, campaign_id, user_id)
    if member is None:
        raise WorkflowError("Campaign membership not found", "not_found")
    if member.role == "master":
        raise WorkflowError("The master must transfer ownership before leaving")
    member.status = "left"
    member.left_at = _now()
    _event(db, campaign.id, user_id, "member_left", {"user_id": str(user_id)})
    master = _master(db, campaign.id)
    create_notification(db, recipient_id=master.user_id, actor_id=user_id, campaign_id=campaign.id, notification_type="member_left", title="Участник покинул кампанию", message=f"Очередная душа покинула «{campaign.name}».", metadata={"username": str(user_id)})
    _commit(db)
    return member


def exclude_member(db: Session, master_id: UUID, campaign_id: UUID, user_id: UUID, reason: str) -> CampaignMember:
    campaign = _require_master(db, campaign_id, master_id)
    member = _active_member(db, campaign_id, user_id)
    if member is None or member.role == "master":
        raise WorkflowError("Player membership not found", "not_found")
    member.status = "excluded"
    member.excluded_at = _now()
    member.exclusion_reason = reason
    _event(db, campaign.id, master_id, "member_excluded", {"user_id": str(user_id), "reason": reason})
    create_notification(db, recipient_id=user_id, actor_id=master_id, campaign_id=campaign.id, notification_type="member_excluded", title="Вы исключены из кампании", message=f"Вы исключены из кампании «{campaign.name}». Причина: {reason}")
    _commit(db)
    return member


def transfer_master(db: Session, master_id: UUID, campaign_id: UUID, new_master_id: UUID) -> None:
    try:
        campaign = _require_master(db, campaign_id, master_id)
        current = _active_member(db, campaign_id, master_id)
        new_master = _active_member(db, campaign_id, new_master_id)
        if current is None or current.role != CampaignRole.MASTER.value:
            raise WorkflowError("Only the campaign master can perform this action", "forbidden")
        if new_master is None:
            raise WorkflowError("New master must be an active campaign member", "not_found")
        if new_master_id == master_id:
            raise WorkflowError("The user is already the campaign master")

        # The partial unique index must never observe two active masters.
        # Flush the demotion before promoting the replacement, while the
        # campaign and both memberships remain locked in this transaction.
        current.role = CampaignRole.PLAYER.value
        db.flush()
        new_master.role = CampaignRole.MASTER.value
        _event(db, campaign.id, master_id, "master_transferred", {"old_master_id": str(master_id), "new_master_id": str(new_master_id)})
        create_notification(db, recipient_id=master_id, actor_id=new_master_id, campaign_id=campaign.id, notification_type="master_transferred", title="Права мастера переданы", message=f"Права мастера кампании «{campaign.name}» переданы.")
        create_notification(db, recipient_id=new_master_id, actor_id=master_id, campaign_id=campaign.id, notification_type="master_transferred", title="Вы стали мастером", message=f"Вы стали мастером кампании «{campaign.name}».")
        _commit(db)
    except Exception:
        db.rollback()
        raise
