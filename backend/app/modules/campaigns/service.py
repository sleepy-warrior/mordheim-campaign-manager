from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import Campaign, CampaignMember, User

from .schemas import CampaignCreate, CampaignRole, CampaignStatus, CampaignStatusUpdate, CampaignUpdate


class CampaignNotFoundError(Exception):
    pass


class CampaignAccessDeniedError(Exception):
    pass


def _load_campaign(db: Session, campaign_id: UUID) -> Campaign:
    campaign = db.scalar(
        select(Campaign)
        .options(joinedload(Campaign.members).joinedload(CampaignMember.user))
        .where(Campaign.id == campaign_id)
    )
    if campaign is None:
        raise CampaignNotFoundError
    return campaign


def _member(campaign: Campaign, user_id: UUID) -> CampaignMember | None:
    return next((member for member in campaign.members if member.user_id == user_id), None)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def create_campaign(db: Session, creator: User, data: CampaignCreate) -> Campaign:
    campaign = Campaign(
        name=data.name,
        description=data.description,
        creator_id=creator.id,
        visibility=data.visibility.value,
        rules_mode=data.rules_mode.value,
        max_bands_per_player=data.max_bands_per_player,
        starting_gold=data.starting_gold,
        max_members=data.max_members,
    )
    campaign.members.append(
        CampaignMember(user_id=creator.id, role=CampaignRole.MASTER.value, user=creator)
    )
    try:
        db.add(campaign)
        _commit(db)
        db.refresh(campaign)
    except IntegrityError:
        db.rollback()
        raise
    return campaign


def list_user_campaigns(db: Session, user_id: UUID) -> list[tuple[Campaign, str]]:
    rows = db.execute(
        select(Campaign, CampaignMember.role)
        .join(CampaignMember, CampaignMember.campaign_id == Campaign.id)
        .where(CampaignMember.user_id == user_id, Campaign.status != CampaignStatus.ARCHIVED.value)
        .order_by(Campaign.created_at.desc())
    ).all()
    return list(rows)


def list_public_campaigns(db: Session) -> list[Campaign]:
    return list(
        db.scalars(
            select(Campaign)
            .where(
                Campaign.visibility == "public",
                Campaign.status != CampaignStatus.ARCHIVED.value,
            )
            .order_by(Campaign.created_at.desc())
        ).all()
    )


def get_campaign(db: Session, campaign_id: UUID, user_id: UUID) -> tuple[Campaign, CampaignMember | None]:
    campaign = _load_campaign(db, campaign_id)
    membership = _member(campaign, user_id)
    if campaign.visibility != "public" and membership is None:
        raise CampaignNotFoundError
    return campaign, membership


def update_campaign(db: Session, campaign_id: UUID, user_id: UUID, data: CampaignUpdate) -> Campaign:
    campaign = _load_campaign(db, campaign_id)
    membership = _member(campaign, user_id)
    if membership is None:
        raise CampaignNotFoundError
    if membership.role != CampaignRole.MASTER.value:
        raise CampaignAccessDeniedError
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value.value if hasattr(value, "value") else value)
    _commit(db)
    db.refresh(campaign)
    return campaign


def update_campaign_status(
    db: Session, campaign_id: UUID, user_id: UUID, data: CampaignStatusUpdate
) -> Campaign:
    campaign = _load_campaign(db, campaign_id)
    membership = _member(campaign, user_id)
    if membership is None:
        raise CampaignNotFoundError
    if membership.role != CampaignRole.MASTER.value:
        raise CampaignAccessDeniedError
    campaign.status = data.status.value
    _commit(db)
    db.refresh(campaign)
    return campaign
