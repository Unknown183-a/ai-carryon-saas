import ComingSoon from "@/components/ComingSoon";

export default function AnalyticsPage() {
  return (
    <ComingSoon
      title="Analytics"
      reason="This reads from the analytics Firestore collection and Qdrant's analytics namespace, which nothing writes to yet — that starts once channels are actually uploading videos (Phase 7/8) and the Learning Agent (Phase 12) is analyzing performance."
    />
  );
}
