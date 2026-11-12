"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "../../context/AuthContext";
import { ApiError, applyJoinRequest } from "../../lib/api";

export function JoinCampaignPage({ token }: { token: string }) {
  const router = useRouter();
  const { accessToken } = useAuth();
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!accessToken) return;
    setMessage("");
    setError("");
  }, [accessToken]);

  async function submit() {
    if (!accessToken) return;
    setSubmitting(true); setError("");
    try {
      await applyJoinRequest(accessToken, token);
      setMessage("Заявка отправлена мастеру. Вы получите уведомление после рассмотрения.");
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "Не удалось отправить заявку.");
    } finally { setSubmitting(false); }
  }

  const returnPath = `/join/${encodeURIComponent(token)}`;
  return <main className="auth-page"><section className="auth-card" aria-labelledby="join-title"><div className="eyebrow">MORDHEIM // INVITATION</div><h1 id="join-title">Вступление в кампанию</h1>{!accessToken ? <><p className="auth-intro">Войдите или зарегистрируйтесь, чтобы подать заявку на вступление.</p><p><Link className="button-link" href={`/login?next=${encodeURIComponent(returnPath)}`}>Войти</Link> <Link href={`/register?next=${encodeURIComponent(returnPath)}`}>Регистрация</Link></p></> : <><p className="auth-intro">Подайте заявку мастеру. Переход по ссылке не добавляет вас автоматически.</p>{message && <p className="form-message form-success" role="status">{message}</p>}{error && <p className="form-message form-error" role="alert">{error}</p>}{!message && <button type="button" onClick={submit} disabled={submitting}>{submitting ? "Отправляем..." : "Подать заявку"}</button>}<p><Link href="/campaigns">Вернуться к кампаниям</Link></p></>}</section></main>;
}
