import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthForm } from "../components/auth/AuthForm";
import { AuthProvider, useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/api";

const { mockPush } = vi.hoisted(() => ({
  mockPush: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    loginUser: vi.fn(),
    registerUser: vi.fn(),
  };
});

import { loginUser, registerUser } from "../lib/api";

const mockedLoginUser = vi.mocked(loginUser);
const mockedRegisterUser = vi.mocked(registerUser);

function renderForm(mode: "login" | "register") {
  return render(
    <AuthProvider>
      <AuthForm mode={mode} />
    </AuthProvider>,
  );
}

function TokenProbe() {
  const { accessToken } = useAuth();
  return <span data-testid="access-token">{accessToken}</span>;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
});

describe("AuthForm", () => {
  it("submits registration data and shows success", async () => {
    mockedRegisterUser.mockResolvedValue({
      id: "user-id",
      email: "player@example.com",
      username: "warband",
      created_at: "2026-11-12T00:00:00Z",
      updated_at: "2026-11-12T00:00:00Z",
    });
    const user = userEvent.setup();
    renderForm("register");

    await user.type(screen.getByLabelText("Email"), "player@example.com");
    await user.type(screen.getByLabelText("Имя пользователя"), "warband");
    await user.type(screen.getByLabelText("Пароль"), "secure-password");
    await user.click(screen.getByRole("button", { name: "Зарегистрироваться" }));

    expect(mockedRegisterUser).toHaveBeenCalledWith({
      email: "player@example.com",
      username: "warband",
      password: "secure-password",
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Регистрация завершена");
  });

  it("stores a successful login token only in memory", async () => {
    mockedLoginUser.mockResolvedValue({ access_token: "access-token", token_type: "bearer" });
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <AuthForm mode="login" />
        <TokenProbe />
      </AuthProvider>,
    );

    await user.type(screen.getByLabelText("Email"), "player@example.com");
    await user.type(screen.getByLabelText("Пароль"), "secure-password");
    await user.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByTestId("access-token")).toHaveTextContent("access-token");
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(await screen.findByRole("status")).toHaveTextContent("Вход выполнен");
    expect(mockPush).toHaveBeenCalledWith("/profile");
  });

  it("shows the API error message", async () => {
    mockedLoginUser.mockRejectedValue(new ApiError("Invalid email or password", 401));
    const user = userEvent.setup();
    renderForm("login");

    await user.type(screen.getByLabelText("Email"), "unknown@example.com");
    await user.type(screen.getByLabelText("Пароль"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });
});
