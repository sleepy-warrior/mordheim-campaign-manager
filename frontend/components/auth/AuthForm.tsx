"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { useAuth } from "../../context/AuthContext";
import { ApiError, loginUser, registerUser } from "../../lib/api";

type AuthFormProps = {
  mode: "login" | "register";
};

export function AuthForm({ mode }: AuthFormProps) {
  const isLogin = mode === "login";
  const { signIn } = useAuth();
  const router = useRouter();
  const nextPath = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("next") : null;
  const safeNextPath = nextPath?.startsWith("/") && !nextPath.startsWith("//") ? nextPath : null;
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setIsSubmitting(true);

    try {
      if (isLogin) {
        const result = await loginUser({ email, password });
        signIn(result.access_token);
        setSuccess("Вход выполнен. Сессия восстановима после обновления страницы.");
        router.push(safeNextPath ?? "/profile");
      } else {
        await registerUser({ email, username, password });
        setSuccess("Регистрация завершена. Теперь войдите в аккаунт.");
        setPassword("");
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "Не удалось связаться с сервером. Попробуйте ещё раз.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-card" aria-labelledby="auth-title">
      <div className="eyebrow">MORDHEIM // CITIES OF THE DAMNED</div>
      <h1 id="auth-title">{isLogin ? "Вернуться в кампанию" : "Вступить в кампанию"}</h1>
      <p className="auth-intro">
        {isLogin
          ? "Войдите, чтобы продолжить путь своей банды."
          : "Создайте учётную запись для управления своей бандой."}
      </p>

      <form onSubmit={handleSubmit} className="auth-form">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        {!isLogin && (
          <>
            <label htmlFor="username">Имя пользователя</label>
            <input
              id="username"
              name="username"
              type="text"
              minLength={3}
              maxLength={100}
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </>
        )}

        <label htmlFor="password">Пароль</label>
        <input
          id="password"
          name="password"
          type="password"
          minLength={isLogin ? undefined : 8}
          autoComplete={isLogin ? "current-password" : "new-password"}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        {error && (
          <p className="form-message form-error" role="alert">
            {error}
          </p>
        )}
        {success && (
          <p className="form-message form-success" role="status">
            {success}
          </p>
        )}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Проверяем..." : isLogin ? "Войти" : "Зарегистрироваться"}
        </button>
      </form>

      <p className="auth-switch">
        {isLogin ? "Ещё нет учётной записи?" : "Уже есть учётная запись?"}{" "}
        <Link href={`${isLogin ? "/register" : "/login"}${safeNextPath ? `?next=${encodeURIComponent(safeNextPath)}` : ""}`}>
          {isLogin ? "Зарегистрироваться" : "Войти"}
        </Link>
      </p>
    </section>
  );
}
