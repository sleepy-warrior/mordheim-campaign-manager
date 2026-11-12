import { CampaignForm } from "../../../components/campaigns/CampaignForm";
import { InternalNavigation } from "../../../components/InternalNavigation";

export default function NewCampaignPage() { return <main className="campaign-page"><InternalNavigation items={[{ href: "/campaigns", label: "← Все кампании" }]} /><section className="campaign-panel"><div className="eyebrow">MORDHEIM // NEW CAMPAIGN</div><h1>Новая кампания</h1><CampaignForm showNavigation={false} /></section></main>; }
