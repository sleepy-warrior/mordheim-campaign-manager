import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { mockPush, mockReplace, mockRouter } = vi.hoisted(() => { const mockPush = vi.fn(); const mockReplace = vi.fn(); return { mockPush, mockReplace, mockRouter: { push: mockPush, replace: mockReplace } }; });
vi.mock("next/navigation", () => ({ useRouter: () => mockRouter }));
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, applyJoinRequest: vi.fn(), createCampaign: vi.fn(), getCampaign: vi.fn(), getCampaignInvitations: vi.fn(), getCampaigns: vi.fn(), getFormerMembers: vi.fn(), getJoinLink: vi.fn(), getJoinRequests: vi.fn(), refreshAccessToken: vi.fn().mockResolvedValue(null), transferMaster: vi.fn() };
});

import { CampaignForm } from "../components/campaigns/CampaignForm";
import { CampaignList } from "../components/campaigns/CampaignList";
import { JoinCampaignPage } from "../components/campaigns/JoinCampaignPage";
import { CampaignDetail } from "../components/campaigns/CampaignDetail";
import { AuthProvider, useAuth } from "../context/AuthContext";
import { applyJoinRequest, createCampaign, getCampaign, getCampaignInvitations, getCampaigns, getFormerMembers, getJoinLink, getJoinRequests, transferMaster } from "../lib/api";

const mockedCreateCampaign = vi.mocked(createCampaign);
const mockedGetCampaigns = vi.mocked(getCampaigns);
const mockedApplyJoinRequest = vi.mocked(applyJoinRequest);
const mockedGetCampaign = vi.mocked(getCampaign);
const mockedTransferMaster = vi.mocked(transferMaster);
const mockedGetFormerMembers = vi.mocked(getFormerMembers);
const mockedGetCampaignInvitations = vi.mocked(getCampaignInvitations);
const mockedGetJoinRequests = vi.mocked(getJoinRequests);
const mockedGetJoinLink = vi.mocked(getJoinLink);

function SignedIn({ children }: { children: React.ReactNode }) {
  const { signIn } = useAuth();
  useEffect(() => signIn("access-token"), [signIn]);
  return children;
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("campaign frontend", () => {
  it("submits campaign creation data and opens the created campaign", async () => {
    mockedCreateCampaign.mockResolvedValue({ id: "campaign-id", name: "Ruins", description: null, visibility: "private", status: "draft", rules_mode: "standard", max_bands_per_player: 1, starting_gold: 500, role: "master", created_at: "now", updated_at: "now" });
    const user = userEvent.setup();
    render(<AuthProvider><SignedIn><CampaignForm /></SignedIn></AuthProvider>);
    await user.type(screen.getByLabelText("Название"), "Ruins");
    await user.click(screen.getByRole("button", { name: "Создать кампанию" }));
    expect(mockedCreateCampaign).toHaveBeenCalledWith("access-token", expect.objectContaining({ name: "Ruins", visibility: "private" }));
    expect(mockPush).toHaveBeenCalledWith("/campaigns/campaign-id");
  });

  it("renders campaigns returned by the backend", async () => {
    mockedGetCampaigns.mockResolvedValue([{ id: "campaign-id", name: "Ruins", description: "A doomed city", visibility: "public", status: "active", rules_mode: "standard", max_bands_per_player: 1, starting_gold: 500, role: "master", created_at: "now", updated_at: "now" }]);
    render(<AuthProvider><SignedIn><CampaignList /></SignedIn></AuthProvider>);
    expect(await screen.findByText("Ruins")).toBeInTheDocument();
    expect(screen.getByText("A doomed city")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Личный кабинет" })).toHaveAttribute("href", "/profile");
  });

  it("redirects an unauthenticated campaign list to login", async () => {
    render(<AuthProvider><CampaignList /></AuthProvider>);
    await vi.waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/login"));
  });

  it("offers a return path for unauthenticated join links", () => {
    render(<AuthProvider><JoinCampaignPage token="join-token" /></AuthProvider>);
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute("href", "/login?next=%2Fjoin%2Fjoin-token");
  });

  it("submits an authenticated join request", async () => {
    mockedApplyJoinRequest.mockResolvedValue({ id: "request-id", campaign_id: "campaign-id", user_id: "user-id", username: "player", status: "pending", created_at: "now" });
    const user = userEvent.setup();
    render(<AuthProvider><SignedIn><JoinCampaignPage token="join-token" /></SignedIn></AuthProvider>);
    await user.click(screen.getByRole("button", { name: "Подать заявку" }));
    expect(mockedApplyJoinRequest).toHaveBeenCalledWith("access-token", "join-token");
    expect(await screen.findByRole("status")).toHaveTextContent("Заявка отправлена");
  });

  it("confirms master transfer, refreshes roles, and shows success", async () => {
    const campaign = { id: "campaign-id", name: "Ruins", description: null, visibility: "private" as const, status: "draft" as const, rules_mode: "standard" as const, max_bands_per_player: 1, starting_gold: 500, max_members: null, role: "master" as const, created_at: "now", updated_at: "now", members: [{ user_id: "master-id", username: "master", role: "master" as const, status: "active", joined_at: "now" }, { user_id: "player-id", username: "player", role: "player" as const, status: "active", joined_at: "now" }] };
    const transferred = { ...campaign, members: [{ ...campaign.members[0], role: "player" as const }, { ...campaign.members[1], role: "master" as const }] };
    mockedGetCampaign.mockResolvedValueOnce(campaign).mockResolvedValueOnce(transferred);
    mockedTransferMaster.mockResolvedValue(undefined);
    mockedGetFormerMembers.mockResolvedValue([]);
    mockedGetCampaignInvitations.mockResolvedValue([]);
    mockedGetJoinRequests.mockResolvedValue([]);
    mockedGetJoinLink.mockResolvedValue(null);
    vi.stubGlobal("confirm", vi.fn(() => true));
    const user = userEvent.setup();
    render(<AuthProvider><SignedIn><CampaignDetail campaignId="campaign-id" /></SignedIn></AuthProvider>);
    expect((await screen.findAllByText("player")).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Передать master" }));
    expect(mockedTransferMaster).toHaveBeenCalledWith("access-token", "campaign-id", "player-id");
    expect(await screen.findByRole("status")).toHaveTextContent("Права мастера переданы");
    expect(screen.getAllByText("player")[0].parentElement).toHaveTextContent("master");
    expect(screen.getByRole("link", { name: "Личный кабинет" })).toHaveAttribute("href", "/profile");
    expect(screen.getByRole("link", { name: "← Все кампании" })).toHaveAttribute("href", "/campaigns");
  });

  it("shows the backend error when master transfer fails", async () => {
    const campaign = { id: "campaign-id", name: "Ruins", description: null, visibility: "private" as const, status: "draft" as const, rules_mode: "standard" as const, max_bands_per_player: 1, starting_gold: 500, max_members: null, role: "master" as const, created_at: "now", updated_at: "now", members: [{ user_id: "master-id", username: "master", role: "master" as const, status: "active", joined_at: "now" }, { user_id: "player-id", username: "player", role: "player" as const, status: "active", joined_at: "now" }] };
    mockedGetCampaign.mockResolvedValue(campaign);
    mockedTransferMaster.mockRejectedValue(new Error("Only the campaign master can perform this action"));
    mockedGetFormerMembers.mockResolvedValue([]);
    mockedGetCampaignInvitations.mockResolvedValue([]);
    mockedGetJoinRequests.mockResolvedValue([]);
    mockedGetJoinLink.mockResolvedValue(null);
    vi.stubGlobal("confirm", vi.fn(() => true));
    const user = userEvent.setup();
    render(<AuthProvider><SignedIn><CampaignDetail campaignId="campaign-id" /></SignedIn></AuthProvider>);
    await user.click(await screen.findByRole("button", { name: "Передать master" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось передать права мастера");
  });
});
