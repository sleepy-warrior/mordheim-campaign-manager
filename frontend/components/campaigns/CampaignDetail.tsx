"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "../../context/AuthContext";
import {
  ApiError, approveJoinRequest, Campaign, CampaignStatus, createJoinLink,
  excludeMember, getCampaign, getCampaignInvitations, getFormerMembers,
  getJoinLink, getJoinRequests, inviteUser, leaveCampaign, rejectJoinRequest,
  searchUsers,
  revokeJoinLink, transferMaster, updateCampaign, updateCampaignStatus,
} from "../../lib/api";
import { InternalNavigation } from "../InternalNavigation";

const statuses: CampaignStatus[] = ["draft", "active", "completed", "archived"];

export function CampaignDetail({ campaignId }: { campaignId: string }) {
  const router = useRouter();
  const { accessToken, isAuthReady } = useAuth();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [formerMembers, setFormerMembers] = useState<Awaited<ReturnType<typeof getFormerMembers>>>([]);
  const [invitations, setInvitations] = useState<Awaited<ReturnType<typeof getCampaignInvitations>>>([]);
  const [requests, setRequests] = useState<Awaited<ReturnType<typeof getJoinRequests>>>([]);
  const [joinUrl, setJoinUrl] = useState<string | null>(null);
  const [activeJoinLink, setActiveJoinLink] = useState(false);
  const [inviteUsername, setInviteUsername] = useState("");

  useEffect(() => {
    if (!isAuthReady) return;
    if (!accessToken) { router.replace("/login"); return; }
    getCampaign(accessToken, campaignId).then(setCampaign).catch((caughtError) => {
      if (caughtError instanceof ApiError && caughtError.status === 401) router.replace("/login");
      else setError(caughtError instanceof ApiError && caughtError.status === 404 ? "Кампания не найдена." : "Не удалось загрузить кампанию.");
    });
  }, [accessToken, campaignId, isAuthReady, router]);

  useEffect(() => {
    if (!accessToken || campaign?.role !== "master") return;
    Promise.all([
      getFormerMembers(accessToken, campaignId).catch(() => []),
      getCampaignInvitations(accessToken, campaignId).catch(() => []),
      getJoinRequests(accessToken, campaignId).catch(() => []),
      getJoinLink(accessToken, campaignId).catch(() => null),
    ]).then(([former, sent, pending, link]) => {
      setFormerMembers(former); setInvitations(sent); setRequests(pending);
      if (link) { setActiveJoinLink(true); if (link.join_url) setJoinUrl(link.join_url); }
    });
  }, [accessToken, campaign?.role, campaignId]);

  async function changeStatus(value: CampaignStatus) {
    if (!accessToken) return;
    try { setCampaign(await updateCampaignStatus(accessToken, campaignId, value)); }
    catch { setError("Не удалось изменить статус кампании."); }
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accessToken || !campaign) return;
    const form = new FormData(event.currentTarget);
    try {
      setCampaign(await updateCampaign(accessToken, campaignId, {
        name: String(form.get("name")), description: String(form.get("description") || ""),
        visibility: String(form.get("visibility")) as "public" | "private",
        rules_mode: String(form.get("rules_mode")) as "standard" | "free",
        max_bands_per_player: Number(form.get("max_bands_per_player")),
        starting_gold: Number(form.get("starting_gold")),
        max_members: form.get("max_members") ? Number(form.get("max_members")) : null,
      }));
    } catch { setError("Не удалось сохранить настройки кампании."); }
  }

  async function reviewRequest(id: string, approve: boolean) {
    if (!accessToken) return;
    try {
      if (approve) await approveJoinRequest(accessToken, campaignId, id); else await rejectJoinRequest(accessToken, campaignId, id);
      setRequests(await getJoinRequests(accessToken, campaignId)); setCampaign(await getCampaign(accessToken, campaignId));
    } catch (caughtError) { setError(caughtError instanceof ApiError ? caughtError.message : "Не удалось обработать заявку."); }
  }

  async function createLink() {
    if (!accessToken) return;
    try { const link = await createJoinLink(accessToken, campaignId); setActiveJoinLink(true); setJoinUrl(link.join_url); }
    catch (caughtError) { setError(caughtError instanceof ApiError ? caughtError.message : "Не удалось создать ссылку."); }
  }

  async function revokeLink() {
    if (!accessToken || !window.confirm("Отозвать общую ссылку?")) return;
    try { await revokeJoinLink(accessToken, campaignId); setJoinUrl(null); setActiveJoinLink(false); } catch { setError("Не удалось отозвать ссылку."); }
  }

  async function sendInvite() {
    if (!accessToken || !inviteUsername) return;
    try { const matches = await searchUsers(accessToken, inviteUsername); if (!matches.some((item) => item.username === inviteUsername)) { setError("Пользователь с таким username не найден."); return; } await inviteUser(accessToken, campaignId, inviteUsername); setInviteUsername(""); setInvitations(await getCampaignInvitations(accessToken, campaignId)); }
    catch (caughtError) { setError(caughtError instanceof ApiError ? caughtError.message : "Не удалось отправить приглашение."); }
  }

  async function leave() {
    if (!accessToken || !window.confirm("Покинуть кампанию?")) return;
    try { await leaveCampaign(accessToken, campaignId); router.replace("/campaigns"); } catch { setError("Не удалось покинуть кампанию."); }
  }

  async function exclude(userId: string) {
    if (!accessToken) return;
    const reason = window.prompt("Причина исключения:");
    if (!reason) return;
    try { await excludeMember(accessToken, campaignId, userId, reason); setCampaign(await getCampaign(accessToken, campaignId)); setFormerMembers(await getFormerMembers(accessToken, campaignId)); }
    catch { setError("Не удалось исключить участника."); }
  }

  async function makeMaster(userId: string) {
    if (!accessToken || !window.confirm("Передать права мастера этому участнику?")) return;
    try {
      await transferMaster(accessToken, campaignId, userId);
      setCampaign(await getCampaign(accessToken, campaignId));
      setError("");
      setNotice("Права мастера переданы.");
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "Не удалось передать права мастера.");
    }
  }

  if (!isAuthReady || !accessToken) return null;
  if (error) return <main className="campaign-page"><InternalNavigation items={[{ href: "/campaigns", label: "← Все кампании" }]} /><p className="form-message form-error" role="alert">{error}</p></main>;
  if (!campaign) return <main className="campaign-page"><InternalNavigation items={[{ href: "/campaigns", label: "← Все кампании" }]} /><p className="auth-intro">Загружаем кампанию...</p></main>;
  const isMaster = campaign.role === "master";

  return <main className="campaign-page">
    <InternalNavigation items={[{ href: "/campaigns", label: "← Все кампании" }]} />
    {notice && <p className="form-message form-success" role="status">{notice}</p>}
    <section className="campaign-panel">
      <div className="eyebrow">{campaign.visibility} // {campaign.rules_mode}</div>
      <h1>{campaign.name}</h1><p className="auth-intro">{campaign.description || "Без описания"}</p>
      <dl className="campaign-facts"><div><dt>Статус</dt><dd>{campaign.status}</dd></div><div><dt>Банд на игрока</dt><dd>{campaign.max_bands_per_player}</dd></div><div><dt>Лимит участников</dt><dd>{campaign.max_members ?? "без лимита"}</dd></div><div><dt>Стартовое золото</dt><dd>{campaign.starting_gold}</dd></div></dl>
      {isMaster && <>
        <div className="campaign-actions"><label>Изменить статус<select value={campaign.status} onChange={(event) => changeStatus(event.target.value as CampaignStatus)}>{statuses.map((item) => <option key={item}>{item}</option>)}</select></label></div>
        <form className="campaign-form" onSubmit={saveSettings}><h2>Настройки мастера</h2><label>Название<input name="name" defaultValue={campaign.name} required /></label><label>Описание<textarea name="description" defaultValue={campaign.description || ""} rows={3} /></label><div className="form-grid"><label>Видимость<select name="visibility" defaultValue={campaign.visibility}><option value="private">Приватная</option><option value="public">Публичная</option></select></label><label>Режим правил<select name="rules_mode" defaultValue={campaign.rules_mode}><option value="standard">Стандартный</option><option value="free">Свободный</option></select></label><label>Банд на игрока<input name="max_bands_per_player" type="number" min={1} defaultValue={campaign.max_bands_per_player} /></label><label>Стартовое золото<input name="starting_gold" type="number" min={0} defaultValue={campaign.starting_gold} /></label><label>Лимит участников<input name="max_members" type="number" min={1} defaultValue={campaign.max_members ?? ""} /></label></div><button type="submit">Сохранить настройки</button></form>
        <section className="campaign-tools" id="join-requests"><h2>Общая ссылка</h2>{joinUrl ? <><input readOnly value={joinUrl} onFocus={(event) => event.currentTarget.select()} /><button type="button" onClick={() => navigator.clipboard?.writeText(joinUrl)}>Копировать</button><button type="button" onClick={revokeLink}>Отозвать</button></> : <button type="button" onClick={createLink}>Создать ссылку</button>}<h2>Пригласить пользователя</h2><input value={inviteUsername} placeholder="Username" onChange={(event) => setInviteUsername(event.target.value)} /><button type="button" onClick={sendInvite}>Отправить приглашение</button>{requests.length > 0 && <><h2>Заявки</h2><ul className="member-list">{requests.map((request) => <li key={request.id}>{request.username}<span>{request.status}</span><button type="button" onClick={() => reviewRequest(request.id, true)}>Принять</button><button type="button" onClick={() => reviewRequest(request.id, false)}>Отклонить</button></li>)}</ul></>}{invitations.length > 0 && <><h2>Отправленные приглашения</h2><ul className="member-list">{invitations.map((invitation) => <li key={invitation.id}>{invitation.username}<span>{invitation.status}</span></li>)}</ul></>}</section>
        <h2>Бывшие участники</h2>{formerMembers.length ? <ul className="member-list">{formerMembers.map((member) => <li key={member.user_id}>{member.username}<span>{member.status === "excluded" ? `Исключён${member.exclusion_reason ? `: ${member.exclusion_reason}` : ""}` : "Покинул кампанию"}</span></li>)}</ul> : <p className="auth-intro">Бывших участников нет.</p>}
      </>}
      {!isMaster && <button type="button" className="secondary-button" onClick={leave}>Покинуть кампанию</button>}
      <h2 id="members">Участники</h2>{campaign.members?.length ? <ul className="member-list">{campaign.members.map((member) => <li key={member.user_id}>{member.username}<span>{member.role}</span>{isMaster && member.role !== "master" && <><button type="button" onClick={() => exclude(member.user_id)}>Исключить</button><button type="button" onClick={() => makeMaster(member.user_id)}>Передать master</button></>}</li>)}</ul> : <p className="auth-intro">Участников пока нет.</p>}
    </section>
  </main>;
}
