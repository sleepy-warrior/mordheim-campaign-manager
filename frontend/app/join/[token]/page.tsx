import { JoinCampaignPage } from "../../../components/campaigns/JoinCampaignPage";

export default async function JoinPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <JoinCampaignPage token={token} />;
}
