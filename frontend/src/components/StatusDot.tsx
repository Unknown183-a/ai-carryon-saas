const STATUS_STYLES: Record<string, { dot: string; label: string; live?: boolean }> = {
  ready: { dot: "bg-signal", label: "Ready" },
  configuring: { dot: "bg-amber", label: "Configuring" },
  running: { dot: "bg-signal", label: "Live", live: true },
  paused: { dot: "bg-slate", label: "Paused" },
  error: { dot: "bg-danger", label: "Error" },
  ok: { dot: "bg-signal", label: "Online", live: true },
  unreachable: { dot: "bg-danger", label: "Unreachable" },
};

export default function StatusDot({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? { dot: "bg-slate", label: status };
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate">
      <span
        className={`h-1.5 w-1.5 rounded-full ${style.dot} ${style.live ? "animate-pulseSignal" : ""}`}
      />
      {style.label}
    </span>
  );
}
