"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "../../context/AuthContext";
import { ApiError, Campaign, getCampaigns } from "../../lib/api";
import { InternalNavigation } from "../InternalNavigation";

export function CampaignList() {
  const router = useRouter();
  const { accessToken, isAuthReady } = useAuth();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!isAuthReady) return;
    if (!accessToken) { router.replace("/login"); return; }
    getCampaigns(accessToken).then(setCampaigns).catch((caughtError) => {
      if (caughtError instanceof ApiError && caughtError.status === 401) router.replace("/login"); else setError("Не удалось загрузить кампании.");
    });
  }, [accessToken, isAuthReady, router]);
  if (!isAuthReady || !accessToken) return null;
  return <main className="campaign-page"><InternalNavigation /><div className="campaign-heading"><div><div className="eyebrow">MORDHEIM // CAMPAIGNS</div><h1>Кампании</h1></div><Link className="button-link" href="/campaigns/new">Новая кампания</Link></div>{error && <p className="form-message form-error" role="alert">{error}</p>}<div className="campaign-grid">{campaigns.map((campaign) => <Link className="campaign-tile" href={`/campaigns/${campaign.id}`} key={campaign.id}><span className="campaign-status">{campaign.status}</span><h2>{campaign.name}</h2><p>{campaign.description || "Без описания"}</p><small>{campaign.role} · {campaign.visibility}</small></Link>)}{campaigns.length === 0 && !error && <p className="auth-intro">У вас пока нет активных кампаний.</p>}</div></main>;
}
