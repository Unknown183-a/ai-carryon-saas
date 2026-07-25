import ComingSoon from "@/components/ComingSoon";

export default function LogsPage() {
  return (
    <ComingSoon
      title="Logs"
      reason="There's no per-run log storage or streaming endpoint on the backend yet — POST /channels/{id}/generate returns a full result once a run finishes, but nothing persists intermediate step-by-step logs anywhere this screen could read them from."
    />
  );
}
