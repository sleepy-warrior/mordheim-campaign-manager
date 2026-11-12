"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "../../context/AuthContext";
import { ApiError, createCampaign } from "../../lib/api";
import { InternalNavigation } from "../InternalNavigation";

export function CampaignForm({ showNavigation = true }: { showNavigation?: boolean }) {
  const router = useRouter();
  const { accessToken } = useAuth();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<"public" | "private">("private");
  const [rulesMode, setRulesMode] = useState<"standard" | "free">("standard");
  const [maxBands, setMaxBands] = useState(1);
  const [startingGold, setStartingGold] = useState(500);
  const [maxMembers, setMaxMembers] = useState<number | "">("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accessToken) { router.replace("/login"); return; }
    setError(""); setSubmitting(true);
    try {
      const campaign = await createCampaign(accessToken, { name, description: description || undefined, visibility, rules_mode: rulesMode, max_bands_per_player: maxBands, starting_gold: startingGold, max_members: maxMembers === "" ? null : maxMembers });
      router.push(`/campaigns/${campaign.id}`);
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "Не удалось создать кампанию.");
    } finally { setSubmitting(false); }
  }

  return <>{showNavigation && <InternalNavigation items={[{ href: "/campaigns", label: "← Все кампании" }]} />}<form className="campaign-form" onSubmit={handleSubmit}>
    <label htmlFor="campaign-name">Название</label>
    <input id="campaign-name" value={name} onChange={(event) => setName(event.target.value)} required maxLength={200} />
    <label htmlFor="campaign-description">Описание</label>
    <textarea id="campaign-description" value={description} onChange={(event) => setDescription(event.target.value)} rows={4} />
    <div className="form-grid">
      <label>Видимость<select value={visibility} onChange={(event) => setVisibility(event.target.value as "public" | "private")}><option value="private">Приватная</option><option value="public">Публичная</option></select></label>
      <label>Режим правил<select value={rulesMode} onChange={(event) => setRulesMode(event.target.value as "standard" | "free")}><option value="standard">Стандартный</option><option value="free">Свободный</option></select></label>
      <label>Банд на игрока<input type="number" min={1} value={maxBands} onChange={(event) => setMaxBands(Number(event.target.value))} /></label>
      <label>Стартовое золото<input type="number" min={0} value={startingGold} onChange={(event) => setStartingGold(Number(event.target.value))} /></label>
      <label>Лимит участников<input type="number" min={1} value={maxMembers} onChange={(event) => setMaxMembers(event.target.value === "" ? "" : Number(event.target.value))} /></label>
    </div>
    {error && <p className="form-message form-error" role="alert">{error}</p>}
    <button type="submit" disabled={submitting}>{submitting ? "Создаём..." : "Создать кампанию"}</button>
  </form></>;
}
