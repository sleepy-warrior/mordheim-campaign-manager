"use client";

import { useEffect, useState } from "react";

import { acceptInvitation, declineInvitation, getMyInvitations, MyInvitation } from "../../lib/api";
import { useAuth } from "../../context/AuthContext";

export function InvitationInbox() {
  const { accessToken } = useAuth();
  const [items, setItems] = useState<MyInvitation[]>([]);
  async function refresh() { if (accessToken) setItems(await getMyInvitations(accessToken)); }
  useEffect(() => { refresh().catch(() => undefined); }, [accessToken]);
  async function respond(id: string, accept: boolean) {
    if (!accessToken) return;
    if (accept) await acceptInvitation(accessToken, id); else await declineInvitation(accessToken, id);
    await refresh();
  }
  if (!items.length) return null;
  return <section className="profile-invitations" id="invitations"><h2>Приглашения в кампании</h2>{items.map((item) => <div className="invitation-card" key={item.id}><span>{item.campaign_name}</span><button type="button" onClick={() => respond(item.id, true)}>Принять</button><button type="button" onClick={() => respond(item.id, false)}>Отклонить</button></div>)}</section>;
}
