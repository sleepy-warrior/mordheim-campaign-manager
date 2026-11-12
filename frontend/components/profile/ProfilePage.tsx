"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "../../context/AuthContext";
import { ApiError, getCurrentUser, UserResponse } from "../../lib/api";
import { NotificationBell } from "../notifications/NotificationBell";
import { InvitationInbox } from "../campaigns/InvitationInbox";
import { InternalNavigation } from "../InternalNavigation";

export function ProfilePage() {
  const router = useRouter();
  const { accessToken, isAuthReady, signOut } = useAuth();
  const [profile, setProfile] = useState<UserResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthReady) return;
    if (!accessToken) {
      router.replace("/login");
      return;
    }

    let cancelled = false;
    getCurrentUser(accessToken)
      .then((user) => {
        if (!cancelled) setProfile(user);
      })
      .catch((caughtError) => {
        if (cancelled) return;
        if (caughtError instanceof ApiError && caughtError.status === 401) {
          signOut();
          router.replace("/login");
          return;
        }
        setError("Не удалось загрузить данные профиля.");
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, isAuthReady, router, signOut]);

  if (!isAuthReady || !accessToken) return null;

  return (
    <main className="internal-page">
      <InternalNavigation />
      <section className="auth-card profile-card" aria-labelledby="profile-title">
        <div className="eyebrow">MORDHEIM // WARBAND RECORD</div>
        <h1 id="profile-title">Личный кабинет</h1>
        <NotificationBell />
        <InvitationInbox />
        {error && (
          <p className="form-message form-error" role="alert">
            {error}
          </p>
        )}
        {!error && !profile && <p className="auth-intro">Читаем записи кампании...</p>}
        {profile && (
          <dl className="profile-details">
            <div>
              <dt>Email</dt>
              <dd>{profile.email}</dd>
            </div>
            <div>
              <dt>Имя пользователя</dt>
              <dd>{profile.username}</dd>
            </div>
          </dl>
        )}
        <div className="profile-actions">
          <Link className="button-link" href="/campaigns">Кампании</Link>
        </div>
      </section>
    </main>
  );
}
