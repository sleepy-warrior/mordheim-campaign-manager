const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type UserCreateInput = {
  email: string;
  username: string;
  password: string;
};

export type LoginInput = {
  email: string;
  password: string;
};

export type UserResponse = {
  id: string;
  email: string;
  username: string;
  created_at: string;
  updated_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
};

export type CampaignVisibility = "public" | "private";
export type CampaignStatus = "draft" | "active" | "completed" | "archived";
export type CampaignRulesMode = "standard" | "free";
export type CampaignRole = "master" | "player";

export type CampaignInput = {
  name: string;
  description?: string;
  visibility: CampaignVisibility;
  rules_mode: CampaignRulesMode;
  max_bands_per_player: number;
  starting_gold: number;
  max_members?: number | null;
};

export type CampaignUpdateInput = Partial<CampaignInput>;

export type CampaignMember = {
  user_id: string;
  username: string;
  role: CampaignRole;
  status?: string;
  joined_at: string;
};

export type Campaign = {
  id: string;
  name: string;
  description: string | null;
  creator_id?: string;
  visibility: CampaignVisibility;
  status: CampaignStatus;
  rules_mode: CampaignRulesMode;
  max_bands_per_player: number;
  starting_gold: number;
  max_members: number | null;
  role: CampaignRole | null;
  created_at: string;
  updated_at: string;
  members?: CampaignMember[];
};

export type JoinLink = { id: string; join_url: string | null; created_at: string; active?: boolean };
export type JoinRequest = { id: string; campaign_id: string; user_id: string; username: string; status: string; created_at: string };
export type Invitation = { id: string; campaign_id: string; user_id: string; username: string; status: string; created_at: string; responded_at?: string | null; revoked_at?: string | null };
export type MyInvitation = { id: string; campaign_id: string; campaign_name: string; status: string; created_at: string };
export type Notification = { id: string; campaign_id: string | null; notification_type: string; title: string; message: string; is_read: boolean; created_at: string; read_at: string | null };
export type FormerMember = CampaignMember & { status: "left" | "excluded"; left_at?: string | null; excluded_at?: string | null; exclusion_reason?: string | null };

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let accessTokenUpdater: ((token: string | null) => void) | null = null;
let refreshPromise: Promise<string | null> | null = null;

export function setAccessTokenUpdater(updater: ((token: string | null) => void) | null): void {
  accessTokenUpdater = updater;
}

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = fetch(`${API_BASE_URL}/api/v1/auth/refresh`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" } })
    .then(async (response) => {
      if (!response.ok) return null;
      const body = await response.json() as TokenResponse;
      return body.access_token;
    })
    .catch(() => null)
    .finally(() => { refreshPromise = null; });
  return refreshPromise;
}

export function logoutSession(): Promise<void> {
  return request<void>("/api/v1/auth/logout", { method: "POST" });
}

async function request<T>(path: string, options: RequestInit, retry = true): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  const hasBearer = Object.entries(options.headers ?? {}).some(([key, value]) => key.toLowerCase() === "authorization" && String(value).startsWith("Bearer "));
  if (response.status === 401 && retry && hasBearer && !path.startsWith("/api/v1/auth/")) {
    const freshToken = await refreshAccessToken();
    if (freshToken) {
      accessTokenUpdater?.(freshToken);
      return request<T>(path, { ...options, headers: { ...options.headers, Authorization: `Bearer ${freshToken}` } }, false);
    }
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join(" ")
      : detail || "Не удалось выполнить запрос.";
    throw new ApiError(message, response.status);
  }

  return body as T;
}

export function registerUser(input: UserCreateInput): Promise<UserResponse> {
  return request<UserResponse>("/api/v1/users/register", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function loginUser(input: LoginInput): Promise<TokenResponse> {
  return request<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getCurrentUser(accessToken: string): Promise<UserResponse> {
  return request<UserResponse>("/api/v1/users/me", {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export function createCampaign(accessToken: string, input: CampaignInput): Promise<Campaign> {
  return request<Campaign>("/api/v1/campaigns", {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify(input),
  });
}

export function getCampaigns(accessToken: string): Promise<Campaign[]> {
  return request<Campaign[]>("/api/v1/campaigns", {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export function getCampaign(accessToken: string, campaignId: string): Promise<Campaign> {
  return request<Campaign>(`/api/v1/campaigns/${campaignId}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export function updateCampaign(
  accessToken: string,
  campaignId: string,
  input: CampaignUpdateInput,
): Promise<Campaign> {
  return request<Campaign>(`/api/v1/campaigns/${campaignId}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify(input),
  });
}

export function updateCampaignStatus(
  accessToken: string,
  campaignId: string,
  status: CampaignStatus,
): Promise<Campaign> {
  return request<Campaign>(`/api/v1/campaigns/${campaignId}/status`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ status }),
  });
}

export function createJoinLink(accessToken: string, campaignId: string): Promise<JoinLink> {
  return request<JoinLink>(`/api/v1/campaigns/${campaignId}/join-link`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
}

export function revokeJoinLink(accessToken: string, campaignId: string): Promise<void> {
  return request<void>(`/api/v1/campaigns/${campaignId}/join-link`, { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } });
}
export function getJoinLink(accessToken: string, campaignId: string): Promise<JoinLink> { return request<JoinLink>(`/api/v1/campaigns/${campaignId}/join-link`, { method: "GET", headers: { Authorization: `Bearer ${accessToken}` } }); }

export function applyJoinRequest(accessToken: string, token: string): Promise<JoinRequest> {
  return request<JoinRequest>(`/api/v1/campaigns/join/${encodeURIComponent(token)}`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
}

export function searchUsers(accessToken: string, username: string): Promise<Array<{ id: string; username: string }>> {
  return request<Array<{ id: string; username: string }>>(`/api/v1/users/search?username=${encodeURIComponent(username)}`, { method: "GET", headers: { Authorization: `Bearer ${accessToken}` } });
}

export function inviteUser(accessToken: string, campaignId: string, username: string): Promise<Invitation> {
  return request<Invitation>(`/api/v1/campaigns/${campaignId}/invitations`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ username }) });
}

export function getCampaignInvitations(accessToken: string, campaignId: string): Promise<Invitation[]> {
  return request<Invitation[]>(`/api/v1/campaigns/${campaignId}/invitations`, { method: "GET", headers: { Authorization: `Bearer ${accessToken}` } });
}

export function revokeInvitation(accessToken: string, campaignId: string, invitationId: string): Promise<Invitation> {
  return request<Invitation>(`/api/v1/campaigns/${campaignId}/invitations/${invitationId}`, { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } });
}

export function acceptInvitation(accessToken: string, invitationId: string): Promise<Invitation> {
  return request<Invitation>(`/api/v1/campaigns/invitations/${invitationId}/accept`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
}

export function declineInvitation(accessToken: string, invitationId: string): Promise<Invitation> {
  return request<Invitation>(`/api/v1/campaigns/invitations/${invitationId}/decline`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
}
export function getMyInvitations(accessToken: string): Promise<MyInvitation[]> { return request<MyInvitation[]>("/api/v1/users/me/invitations", { method: "GET", headers: { Authorization: `Bearer ${accessToken}` } }); }

export function getJoinRequests(accessToken: string, campaignId: string): Promise<JoinRequest[]> { return request<JoinRequest[]>(`/api/v1/campaigns/${campaignId}/join-requests`, { method: "GET", headers: { Authorization: `Bearer ${accessToken}` } }); }
export function approveJoinRequest(accessToken: string, campaignId: string, id: string): Promise<JoinRequest> { return request<JoinRequest>(`/api/v1/campaigns/${campaignId}/join-requests/${id}/approve`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } }); }
export function rejectJoinRequest(accessToken: string, campaignId: string, id: string): Promise<JoinRequest> { return request<JoinRequest>(`/api/v1/campaigns/${campaignId}/join-requests/${id}/reject`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } }); }
export function getFormerMembers(accessToken: string, campaignId: string): Promise<FormerMember[]> { return request<FormerMember[]>(`/api/v1/campaigns/${campaignId}/members/former`, { method: "GET", headers: { Authorization: `Bearer ${accessToken}` } }); }
export function leaveCampaign(accessToken: string, campaignId: string): Promise<CampaignMember> { return request<CampaignMember>(`/api/v1/campaigns/${campaignId}/leave`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } }); }
export function excludeMember(accessToken: string, campaignId: string, userId: string, reason: string): Promise<CampaignMember> { return request<CampaignMember>(`/api/v1/campaigns/${campaignId}/members/${userId}/exclude`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ reason }) }); }
export function transferMaster(accessToken: string, campaignId: string, newMasterId: string): Promise<void> { return request<void>(`/api/v1/campaigns/${campaignId}/transfer-master?new_master_id=${encodeURIComponent(newMasterId)}`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } }); }

export function getNotifications(accessToken: string): Promise<Notification[]> {
  return request<Notification[]>("/api/v1/notifications", { method: "GET", headers: { Authorization: `Bearer ${accessToken}` } });
}

export function markNotificationRead(accessToken: string, notificationId: string): Promise<Notification> {
  return request<Notification>(`/api/v1/notifications/${notificationId}/read`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
}

export function markAllNotificationsRead(accessToken: string): Promise<void> {
  return request<void>("/api/v1/notifications/read-all", { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
}

export function clearNotifications(accessToken: string): Promise<void> {
  return request<void>("/api/v1/notifications", { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } });
}
