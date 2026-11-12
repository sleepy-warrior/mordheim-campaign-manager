import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { mockReplace, mockPush } = vi.hoisted(() => ({ mockReplace: vi.fn(), mockPush: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: mockPush }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, getCurrentUser: vi.fn(), getNotifications: vi.fn().mockResolvedValue([]), markNotificationRead: vi.fn(), refreshAccessToken: vi.fn().mockResolvedValue(null) };
});

import { ProfilePage } from "../components/profile/ProfilePage";
import { AuthProvider, useAuth } from "../context/AuthContext";
import { getCurrentUser, getNotifications, markNotificationRead } from "../lib/api";

const mockedGetCurrentUser = vi.mocked(getCurrentUser);
const mockedGetNotifications = vi.mocked(getNotifications);
const mockedMarkNotificationRead = vi.mocked(markNotificationRead);

function SignedIn({ children }: { children: React.ReactNode }) {
  const { signIn } = useAuth();
  useEffect(() => signIn("access-token"), [signIn]);
  return children;
}

function renderSignedInProfile() {
  return render(
    <AuthProvider>
      <SignedIn>
        <ProfilePage />
      </SignedIn>
    </AuthProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ProfilePage", () => {
  it("shows current user data returned by backend", async () => {
    mockedGetCurrentUser.mockResolvedValue({
      id: "user-id",
      email: "backend@example.com",
      username: "backend_user",
      created_at: "2026-11-12T00:00:00Z",
      updated_at: "2026-11-12T00:00:00Z",
    });

    renderSignedInProfile();

    expect(await screen.findByText("backend@example.com")).toBeInTheDocument();
    expect(screen.getByText("backend_user")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Кампании" })).toHaveAttribute("href", "/campaigns");
    expect(screen.getByRole("link", { name: "Кампании" }).parentElement).toHaveClass("profile-actions");
    expect(mockedGetCurrentUser).toHaveBeenCalledWith("access-token");
  });

  it("redirects unauthenticated users to login", async () => {
    render(
      <AuthProvider>
        <ProfilePage />
      </AuthProvider>,
    );

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/login"));
  });

  it("clears the in-memory token and redirects on logout", async () => {
    mockedGetCurrentUser.mockResolvedValue({
      id: "user-id",
      email: "backend@example.com",
      username: "backend_user",
      created_at: "2026-11-12T00:00:00Z",
      updated_at: "2026-11-12T00:00:00Z",
    });
    const user = userEvent.setup();
    renderSignedInProfile();

    await screen.findByText("backend@example.com");
    await user.click(screen.getByRole("button", { name: "Выйти" }));

    expect(mockReplace).toHaveBeenCalledWith("/login");
  });

  it("renders the gothic notification bell without an unread marker when empty", async () => {
    mockedGetCurrentUser.mockResolvedValue({
      id: "user-id", email: "backend@example.com", username: "backend_user",
      created_at: "2026-11-12T00:00:00Z", updated_at: "2026-11-12T00:00:00Z",
    });
    renderSignedInProfile();
    const bell = await screen.findByRole("button", { name: "Уведомления" });
    expect(bell.querySelector("svg")).toBeInTheDocument();
    expect(bell.querySelector(".notification-dot")).not.toBeInTheDocument();
  });

  it("shows an unread marker and keeps polling notifications", async () => {
    mockedGetCurrentUser.mockResolvedValue({ id: "user-id", email: "backend@example.com", username: "backend_user", created_at: "2026-11-12T00:00:00Z", updated_at: "2026-11-12T00:00:00Z" });
    mockedGetNotifications.mockResolvedValue([{ id: "notification-id", campaign_id: null, notification_type: "test", title: "Новое", message: "Событие", is_read: false, created_at: "2026-11-12T00:00:00Z", read_at: null }]);
    renderSignedInProfile();
    const bell = await screen.findByRole("button", { name: "Уведомления" });
    await vi.waitFor(() => expect(bell.querySelector(".notification-dot")).toBeInTheDocument());
    expect(bell).toHaveClass("bell-unread");
  });

  it("marks a campaign notification read before navigating to its section", async () => {
    mockedGetCurrentUser.mockResolvedValue({ id: "user-id", email: "backend@example.com", username: "backend_user", created_at: "2026-11-12T00:00:00Z", updated_at: "2026-11-12T00:00:00Z" });
    mockedGetNotifications.mockResolvedValue([{ id: "notification-id", campaign_id: "campaign-id", notification_type: "join_request", title: "Новая заявка", message: "Заявка", is_read: false, created_at: "2026-11-12T00:00:00Z", read_at: null }]);
    mockedMarkNotificationRead.mockResolvedValue({ id: "notification-id", campaign_id: "campaign-id", notification_type: "join_request", title: "Новая заявка", message: "Заявка", is_read: true, created_at: "2026-11-12T00:00:00Z", read_at: "2026-11-12T00:00:01Z" });
    const user = userEvent.setup();
    renderSignedInProfile();
    await user.click(await screen.findByRole("button", { name: "Уведомления" }));
    await user.click(screen.getByRole("button", { name: /Новая заявка/ }));
    expect(mockedMarkNotificationRead).toHaveBeenCalledWith("access-token", "notification-id");
    expect(mockPush).toHaveBeenCalledWith("/campaigns/campaign-id#join-requests");
  });

  it("routes invitations to the profile inbox", async () => {
    mockedGetCurrentUser.mockResolvedValue({ id: "user-id", email: "backend@example.com", username: "backend_user", created_at: "2026-11-12T00:00:00Z", updated_at: "2026-11-12T00:00:00Z" });
    mockedGetNotifications.mockResolvedValue([{ id: "notification-id", campaign_id: "campaign-id", notification_type: "invitation", title: "Приглашение", message: "Вас пригласили", is_read: true, created_at: "2026-11-12T00:00:00Z", read_at: null }]);
    const user = userEvent.setup();
    renderSignedInProfile();
    await user.click(await screen.findByRole("button", { name: "Уведомления" }));
    await user.click(screen.getByRole("button", { name: /Приглашение/ }));
    expect(mockPush).toHaveBeenCalledWith("/profile#invitations");
  });
});
