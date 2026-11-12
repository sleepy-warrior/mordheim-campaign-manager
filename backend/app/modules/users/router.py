from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.session import get_db
from app.models import CampaignInvitation, CampaignJoinRequest, User
from app.modules.auth.dependencies import get_current_user

from .schemas import UserCreate, UserResponse, UserSearchResponse
from .service import UserAlreadyExistsError, register_user, search_users


router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user_data: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    try:
        return register_user(db, user_data)
    except UserAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return current_user


@router.get("/search", response_model=list[UserSearchResponse])
def search(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserSearchResponse]:
    return search_users(db, username, current_user.id)


@router.get("/me/join-requests")
def my_join_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    requests = db.scalars(
        select(CampaignJoinRequest)
        .where(CampaignJoinRequest.user_id == current_user.id, CampaignJoinRequest.status == "pending")
        .order_by(CampaignJoinRequest.created_at.desc())
    ).all()
    return requests


@router.get("/me/invitations")
def my_invitations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    invitations = db.scalars(
        select(CampaignInvitation)
        .options(joinedload(CampaignInvitation.campaign))
        .where(CampaignInvitation.user_id == current_user.id, CampaignInvitation.status == "pending")
        .order_by(CampaignInvitation.created_at.desc())
    ).all()
    return [
        {
            "id": invitation.id,
            "campaign_id": invitation.campaign_id,
            "campaign_name": invitation.campaign.name,
            "status": invitation.status,
            "created_at": invitation.created_at,
        }
        for invitation in invitations
    ]
