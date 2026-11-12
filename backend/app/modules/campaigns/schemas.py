from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CampaignVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CampaignRulesMode(StrEnum):
    STANDARD = "standard"
    FREE = "free"


class CampaignRole(StrEnum):
    MASTER = "master"
    PLAYER = "player"


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    visibility: CampaignVisibility = CampaignVisibility.PRIVATE
    rules_mode: CampaignRulesMode = CampaignRulesMode.STANDARD
    max_bands_per_player: int = Field(default=1, ge=1)
    starting_gold: int = Field(default=500, ge=0)
    max_members: int | None = Field(default=None, ge=1)


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    visibility: CampaignVisibility | None = None
    rules_mode: CampaignRulesMode | None = None
    max_bands_per_player: int | None = Field(default=None, ge=1)
    starting_gold: int | None = Field(default=None, ge=0)
    max_members: int | None = Field(default=None, ge=1)


class CampaignStatusUpdate(BaseModel):
    status: CampaignStatus


class CampaignMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    username: str
    role: CampaignRole
    status: str = "active"
    joined_at: datetime


class FormerCampaignMemberResponse(CampaignMemberResponse):
    status: str
    left_at: datetime | None = None
    excluded_at: datetime | None = None
    exclusion_reason: str | None = None


class JoinLinkResponse(BaseModel):
    id: UUID
    join_url: str | None = None
    created_at: datetime
    active: bool = True


class JoinRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    user_id: UUID
    username: str
    status: str
    created_at: datetime


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    user_id: UUID
    username: str
    status: str
    created_at: datetime
    responded_at: datetime | None = None
    revoked_at: datetime | None = None


class InviteUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)


class ExcludeMemberRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class UserSearchResponse(BaseModel):
    id: UUID
    username: str


class CampaignSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    visibility: CampaignVisibility
    status: CampaignStatus
    rules_mode: CampaignRulesMode
    max_bands_per_player: int
    starting_gold: int
    max_members: int | None = None
    role: CampaignRole | None = None
    created_at: datetime
    updated_at: datetime


class CampaignResponse(CampaignSummary):
    creator_id: UUID
    members: list[CampaignMemberResponse] = Field(default_factory=list)
