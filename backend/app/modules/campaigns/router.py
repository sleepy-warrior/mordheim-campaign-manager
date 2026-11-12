from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.modules.auth.dependencies import get_current_user

import os

from .schemas import (
    CampaignCreate, CampaignMemberResponse, CampaignResponse, CampaignStatusUpdate,
    CampaignSummary, ExcludeMemberRequest, FormerCampaignMemberResponse,
    InvitationResponse, InviteUserRequest, JoinLinkResponse, JoinRequestResponse,
    CampaignUpdate,
)
from .service import (
    CampaignAccessDeniedError,
    CampaignNotFoundError,
    create_campaign,
    get_campaign,
    list_public_campaigns,
    list_user_campaigns,
    update_campaign,
    update_campaign_status,
)
from .workflow_service import (
    WorkflowError, apply_join_request, create_join_link, exclude_member,
    invite_user, leave_campaign, respond_invitation, review_join_request,
    revoke_invitation, revoke_join_link, transfer_master, _require_master,
)
from app.models import CampaignInvitation, CampaignJoinLink, CampaignJoinRequest, CampaignMember, User
from sqlalchemy import select
from sqlalchemy.orm import joinedload

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


def _response(campaign, role=None, include_members=True):
    members = []
    if include_members:
        visible_members = campaign.members if role == "master" else [member for member in campaign.members if member.status == "active"]
        members = [
            {"user_id": member.user_id, "username": member.user.username, "role": member.role, "status": member.status, "joined_at": member.joined_at}
            for member in visible_members
        ]
    return CampaignResponse.model_validate({
        "id": campaign.id, "name": campaign.name, "description": campaign.description,
        "visibility": campaign.visibility, "status": campaign.status, "rules_mode": campaign.rules_mode,
        "max_bands_per_player": campaign.max_bands_per_player, "starting_gold": campaign.starting_gold, "max_members": campaign.max_members,
        "role": role, "created_at": campaign.created_at, "updated_at": campaign.updated_at,
        "creator_id": campaign.creator_id, "members": members,
    })


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create(data: CampaignCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _response(create_campaign(db, user, data), role="master")


@router.get("", response_model=list[CampaignSummary])
def list_mine(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [
        CampaignSummary.model_validate({
            "id": campaign.id, "name": campaign.name, "description": campaign.description,
            "visibility": campaign.visibility, "status": campaign.status, "rules_mode": campaign.rules_mode,
            "max_bands_per_player": campaign.max_bands_per_player, "starting_gold": campaign.starting_gold, "max_members": campaign.max_members,
            "role": role, "created_at": campaign.created_at, "updated_at": campaign.updated_at,
        })
        for campaign, role in list_user_campaigns(db, user.id)
    ]


@router.get("/public", response_model=list[CampaignSummary])
def list_public(db: Session = Depends(get_db)):
    return [CampaignSummary.model_validate(campaign) for campaign in list_public_campaigns(db)]


def _workflow_error(error: WorkflowError) -> HTTPException:
    code_to_status = {"not_found": status.HTTP_404_NOT_FOUND, "forbidden": status.HTTP_403_FORBIDDEN, "limit": status.HTTP_409_CONFLICT}
    return HTTPException(status_code=code_to_status.get(error.code, status.HTTP_409_CONFLICT), detail=error.message)


def _invitation_response(item):
    return {
        "id": item.id, "campaign_id": item.campaign_id, "user_id": item.user_id,
        "username": item.user.username, "status": item.status,
        "created_at": item.created_at, "responded_at": item.responded_at,
        "revoked_at": item.revoked_at,
    }


def _member_response(item):
    return {
        "user_id": item.user_id, "username": item.user.username, "role": item.role,
        "status": item.status, "joined_at": item.joined_at,
    }


@router.post("/join/{token}", response_model=JoinRequestResponse, status_code=status.HTTP_201_CREATED)
def apply_join(token: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        request = apply_join_request(db, user.id, token)
    except WorkflowError as error:
        raise _workflow_error(error) from error
    return {"id": request.id, "campaign_id": request.campaign_id, "user_id": request.user_id, "username": user.username, "status": request.status, "created_at": request.created_at}


@router.post("/{campaign_id}/join-link", response_model=JoinLinkResponse, status_code=status.HTTP_201_CREATED)
def create_link(campaign_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        link, token = create_join_link(db, user.id, campaign_id)
    except WorkflowError as error:
        raise _workflow_error(error) from error
    base_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return {"id": link.id, "join_url": f"{base_url}/join/{token}", "created_at": link.created_at}


@router.delete("/{campaign_id}/join-link", status_code=status.HTTP_204_NO_CONTENT)
def revoke_link(campaign_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    try:
        revoke_join_link(db, user.id, campaign_id)
    except WorkflowError as error:
        raise _workflow_error(error) from error


@router.get("/{campaign_id}/join-link", response_model=JoinLinkResponse)
def get_link(campaign_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        _require_master(db, campaign_id, user.id)
    except WorkflowError as error:
        raise _workflow_error(error) from error
    link = db.scalar(select(CampaignJoinLink).where(CampaignJoinLink.campaign_id == campaign_id, CampaignJoinLink.revoked_at.is_(None)))
    if link is None:
        raise HTTPException(status_code=404, detail="Active join link not found")
    return {"id": link.id, "join_url": None, "created_at": link.created_at, "active": True}


@router.get("/{campaign_id}/join-requests", response_model=list[JoinRequestResponse])
def get_join_requests(campaign_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        _require_master(db, campaign_id, user.id)
    except WorkflowError as error:
        raise _workflow_error(error) from error
    requests = db.scalars(select(CampaignJoinRequest).options(joinedload(CampaignJoinRequest.user)).where(CampaignJoinRequest.campaign_id == campaign_id, CampaignJoinRequest.status == "pending")).all()
    return [{"id": item.id, "campaign_id": item.campaign_id, "user_id": item.user_id, "username": item.user.username, "status": item.status, "created_at": item.created_at} for item in requests]


@router.post("/{campaign_id}/join-requests/{request_id}/approve", response_model=JoinRequestResponse)
def approve_request(campaign_id: UUID, request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        request = review_join_request(db, user.id, request_id, True)
    except WorkflowError as error:
        raise _workflow_error(error) from error
    joined_user = db.get(User, request.user_id)
    return {"id": request.id, "campaign_id": campaign_id, "user_id": request.user_id, "username": joined_user.username, "status": request.status, "created_at": request.created_at}


@router.post("/{campaign_id}/join-requests/{request_id}/reject", response_model=JoinRequestResponse)
def reject_request(campaign_id: UUID, request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        request = review_join_request(db, user.id, request_id, False)
    except WorkflowError as error:
        raise _workflow_error(error) from error
    joined_user = db.get(User, request.user_id)
    return {"id": request.id, "campaign_id": campaign_id, "user_id": request.user_id, "username": joined_user.username, "status": request.status, "created_at": request.created_at}


@router.post("/{campaign_id}/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(campaign_id: UUID, data: InviteUserRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invited = db.scalar(select(User).where(User.username == data.username))
    if invited is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        invitation = invite_user(db, user.id, campaign_id, invited)
    except WorkflowError as error:
        raise _workflow_error(error) from error
    return {"id": invitation.id, "campaign_id": invitation.campaign_id, "user_id": invited.id, "username": invited.username, "status": invitation.status, "created_at": invitation.created_at, "responded_at": invitation.responded_at, "revoked_at": invitation.revoked_at}


@router.get("/{campaign_id}/invitations", response_model=list[InvitationResponse])
def get_invitations(campaign_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        _require_master(db, campaign_id, user.id)
    except WorkflowError as error:
        raise _workflow_error(error) from error
    invitations = db.scalars(select(CampaignInvitation).options(joinedload(CampaignInvitation.user)).where(CampaignInvitation.campaign_id == campaign_id).order_by(CampaignInvitation.created_at.desc())).all()
    return [{"id": item.id, "campaign_id": item.campaign_id, "user_id": item.user_id, "username": item.user.username, "status": item.status, "created_at": item.created_at, "responded_at": item.responded_at, "revoked_at": item.revoked_at} for item in invitations]


@router.post("/invitations/{invitation_id}/accept", response_model=InvitationResponse)
def accept_invitation(invitation_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        invitation = respond_invitation(db, user.id, invitation_id, True)
    except WorkflowError as error:
        raise _workflow_error(error) from error
    invitation.user = user
    return _invitation_response(invitation)


@router.post("/invitations/{invitation_id}/decline", response_model=InvitationResponse)
def decline_invitation(invitation_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        invitation = respond_invitation(db, user.id, invitation_id, False)
    except WorkflowError as error:
        raise _workflow_error(error) from error
    invitation.user = user
    return _invitation_response(invitation)


@router.delete("/{campaign_id}/invitations/{invitation_id}", response_model=InvitationResponse)
def revoke_invitation_endpoint(campaign_id: UUID, invitation_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        invitation = revoke_invitation(db, user.id, invitation_id)
        invitation.user = db.get(User, invitation.user_id)
        return _invitation_response(invitation)
    except WorkflowError as error:
        raise _workflow_error(error) from error


@router.get("/{campaign_id}/members", response_model=list[CampaignMemberResponse])
def get_members(campaign_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        campaign, membership = get_campaign(db, campaign_id, user.id)
    except CampaignNotFoundError as error:
        raise HTTPException(status_code=404, detail="Campaign not found") from error
    members = db.scalars(select(CampaignMember).options(joinedload(CampaignMember.user)).where(CampaignMember.campaign_id == campaign_id, CampaignMember.status == "active")).all()
    return [{"user_id": item.user_id, "username": item.user.username, "role": item.role, "status": item.status, "joined_at": item.joined_at} for item in members]


@router.get("/{campaign_id}/members/former", response_model=list[FormerCampaignMemberResponse])
def get_former_members(campaign_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        _require_master(db, campaign_id, user.id)
    except WorkflowError as error:
        raise _workflow_error(error) from error
    members = db.scalars(select(CampaignMember).options(joinedload(CampaignMember.user)).where(CampaignMember.campaign_id == campaign_id, CampaignMember.status.in_(["left", "excluded"]))).all()
    return [{"user_id": item.user_id, "username": item.user.username, "role": item.role, "status": item.status, "joined_at": item.joined_at, "left_at": item.left_at, "excluded_at": item.excluded_at, "exclusion_reason": item.exclusion_reason} for item in members]


@router.post("/{campaign_id}/leave", response_model=CampaignMemberResponse)
def leave(campaign_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        member = leave_campaign(db, user.id, campaign_id)
        member.user = user
        return _member_response(member)
    except WorkflowError as error:
        raise _workflow_error(error) from error


@router.post("/{campaign_id}/members/{member_id}/exclude", response_model=CampaignMemberResponse)
def exclude(campaign_id: UUID, member_id: UUID, data: ExcludeMemberRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        member = exclude_member(db, user.id, campaign_id, member_id, data.reason)
        member.user = db.get(User, member.user_id)
        return _member_response(member)
    except WorkflowError as error:
        raise _workflow_error(error) from error


@router.post("/{campaign_id}/transfer-master", status_code=status.HTTP_204_NO_CONTENT)
def transfer(campaign_id: UUID, new_master_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    try:
        transfer_master(db, user.id, campaign_id, new_master_id)
    except WorkflowError as error:
        raise _workflow_error(error) from error


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_one(campaign_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        campaign, membership = get_campaign(db, campaign_id, user.id)
    except CampaignNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found") from error
    return _response(campaign, membership.role if membership else None, include_members=membership is not None)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update(campaign_id: UUID, data: CampaignUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        campaign = update_campaign(db, campaign_id, user.id, data)
    except CampaignNotFoundError as error:
        raise HTTPException(status_code=404, detail="Campaign not found") from error
    except CampaignAccessDeniedError as error:
        raise HTTPException(status_code=403, detail="Only the campaign master can update it") from error
    return _response(campaign, role="master")


@router.patch("/{campaign_id}/status", response_model=CampaignResponse)
def update_status(campaign_id: UUID, data: CampaignStatusUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        campaign = update_campaign_status(db, campaign_id, user.id, data)
    except CampaignNotFoundError as error:
        raise HTTPException(status_code=404, detail="Campaign not found") from error
    except CampaignAccessDeniedError as error:
        raise HTTPException(status_code=403, detail="Only the campaign master can change status") from error
    return _response(campaign, role="master")
