"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiFetch, fetchHealth } from "@/lib/api";
import type { Channel, GenerateRunResult, ScheduleInfo } from "@/lib/types";
import StatusDot from "@/components/StatusDot";

// Ch.03 describes WS /ws/pipeline/{run_id} for real-time progress, but
// that endpoint isn't built yet (no websocket router in app/api — only
// REST). Until it exists, this polls /health as the live signal and
// treats a run as a single blocking call, per what POST
// /channels/{id}/generate actually does today. Swap the polling block
// below for a `new WebSocket(...)` connection once Ch.03's route ships —
// nothing else on this page needs to change.
const POLL_INTERVAL_MS = 15_000;

export default function ChannelDetailPage() {
  // Static export freezes the `params` prop to build time (only the
  // placeholder id from generateStaticParams()) -- useParams() instead
  // reads the browser's actual current URL client-side after hydration,
  // so this works for any real channel id.
  const searchParams = useSearchParams();
  const params = { id: searchParams.get("id") ?? "" };
  const [channel, setChannel] = useState<Channel | null>(null);
  const [schedule, setSchedule] = useState<ScheduleInfo | null>(null);
  const [gatewayUp, setGatewayUp] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<GenerateRunResult | null>(null);

  const loadChannel = useCallback(async () => {
    try {
      const all = await apiFetch<Channel[]>("/channels");
      const found = all.find((c) => c.channel_id === params.id) ?? null;
      setChannel(found);
      if (!found) {
        setError("This channel wasn't found in your workspace.");
        return;
      }
      // Schedule is fetched separately from /channels — a channel with
      // no schedules doc yet (see backend's get_channel_schedule) is a
      // valid, displayable state, not an error, so this never blocks
      // the rest of the page on failure.
      try {
        setSchedule(await apiFetch<ScheduleInfo>(`/channels/${found.channel_id}/schedule`));
      } catch {
        setSchedule(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this channel.");
    }
  }, [params.id]);

  useEffect(() => {
    loadChannel();
  }, [loadChannel]);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        await fetchHealth();
        if (!cancelled) setGatewayUp(true);
      } catch {
        if (!cancelled) setGatewayUp(false);
      }
    }
    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  async function handleGenerate() {
    setRunning(true);
    setRunError(null);
    try {
      const result = await apiFetch<GenerateRunResult>(`/channels/${params.id}/generate`, {
        method: "POST",
      });
      setLastRun(result);
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "Run failed.");
    } finally {
      setRunning(false);
    }
  }

  if (error) {
    return (
      <div className="max-w-3xl">
        <Link href="/channels" className="text-xs text-slate hover:text-paper">
          ← Channels
        </Link>
        <p className="mt-4 rounded-md border border-danger/30 bg-dangerDim px-4 py-3 text-sm text-danger">
          {error}
        </p>
      </div>
    );
  }

  if (!channel) {
    return <p className="text-sm text-slate">Loading channel…</p>;
  }

  return (
    <div className="max-w-3xl">
      <Link href="/channels" className="text-xs text-slate hover:text-paper">
        ← Channels
      </Link>

      <header className="mt-4 mb-8 flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-paper">{channel.name}</h1>
          <p className="mt-1 font-mono text-xs text-slate">{channel.channel_id}</p>
        </div>
        <StatusDot status={channel.status} />
      </header>

      <div className="mb-6 grid grid-cols-2 gap-4">
        <InfoCard label="Category" value={channel.category} />
        <InfoCard label="Format" value={channel.format} />
        <InfoCard label="Language / Country" value={`${channel.language.toUpperCase()} · ${channel.country}`} />
        <InfoCard label="Upload schedule" value={channel.upload_schedule.replace(/_/g, " ")} />
        <NextRunCard schedule={schedule} />
        <InfoCard
          label="Last auto-run"
          value={schedule?.last_run_at ? formatAbsolute(schedule.last_run_at) : "Never"}
        />
      </div>

      <div className="panel mb-6 p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="font-display text-sm font-semibold text-paper">Live status</h2>
            <p className="mt-1 text-xs text-slate">
              Polling the gateway every {POLL_INTERVAL_MS / 1000}s.
            </p>
          </div>
          <StatusDot status={gatewayUp === null ? "configuring" : gatewayUp ? "ok" : "unreachable"} />
        </div>

        <button onClick={handleGenerate} disabled={running} className="btn-primary">
          {running ? "Running pipeline…" : "Generate now"}
        </button>

        {runError && (
          <p className="mt-4 rounded-md border border-danger/30 bg-dangerDim px-4 py-3 text-sm text-danger">
            {runError}
          </p>
        )}

        {lastRun && (
          <div className="mt-5 space-y-3 border-t border-line pt-5">
            <Row label="Run ID" value={lastRun.run_id} mono />
            <Row label="Topic" value={String(lastRun.topic ?? "—")} />
            <Row
              label="Review"
              value={lastRun.review_verdict ?? "—"}
              tone={lastRun.review_verdict === "fail" ? "danger" : "signal"}
            />
            {lastRun.failure_reason && <Row label="Failure reason" value={lastRun.failure_reason} tone="danger" />}
            <Row label="Render status" value={lastRun.render_status ?? "not enqueued"} />
            {lastRun.render_task_id && <Row label="Render task" value={lastRun.render_task_id} mono />}
            {lastRun.render_failure_reason && (
              <Row label="Render failure reason" value={lastRun.render_failure_reason} tone="danger" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="panel p-4">
      <p className="text-xs uppercase tracking-wide text-slate">{label}</p>
      <p className="mt-1.5 text-sm capitalize text-paper">{value}</p>
    </div>
  );
}

/** Renders in the browser's own local timezone — the schedule doc
 * stores UTC ISO strings (same convention as everywhere else in this
 * project), so this is the one place that converts for display. */
function formatAbsolute(isoUtc: string): string {
  const date = new Date(isoUtc);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** "in 2h 15m" / "in 40m" / "overdue" — overdue means next_run_at is in
 * the past, which in a healthy system only happens for the few seconds
 * between a slot arriving and the scheduler's next poll (it runs every
 * 30 min, see .github/workflows/scheduler.yml) — anything overdue by
 * much longer than that is worth a second look. */
function formatRelative(isoUtc: string, now: Date): string {
  const target = new Date(isoUtc);
  if (Number.isNaN(target.getTime())) return "";
  const diffMs = target.getTime() - now.getTime();
  if (diffMs <= 0) return "overdue";

  const totalMinutes = Math.round(diffMs / 60_000);
  const days = Math.floor(totalMinutes / (24 * 60));
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) return `in ${days}d ${hours}h`;
  if (hours > 0) return `in ${hours}h ${minutes}m`;
  return `in ${minutes}m`;
}

function NextRunCard({ schedule }: { schedule: ScheduleInfo | null }) {
  // Re-renders the relative "in Xh Ym" text once a minute so it doesn't
  // go stale while the page sits open — cheap, since it's just a
  // re-render, not a re-fetch.
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(interval);
  }, []);

  let value: string;
  let tone: "danger" | "signal" | undefined;

  if (!schedule || !schedule.next_run_at) {
    value = "Not scheduled";
  } else if (schedule.enabled === false) {
    value = "Auto-scheduling paused";
    tone = "danger";
  } else {
    const relative = formatRelative(schedule.next_run_at, now);
    value = `${formatAbsolute(schedule.next_run_at)} (${relative})`;
    tone = relative === "overdue" ? "danger" : "signal";
  }

  const toneClass = tone === "danger" ? "text-danger" : tone === "signal" ? "text-signal" : "text-paper";

  return (
    <div className="panel p-4">
      <p className="text-xs uppercase tracking-wide text-slate">Next auto-run</p>
      <p className={`mt-1.5 text-sm ${toneClass}`}>{value}</p>
    </div>
  );
}

function Row({
  label,
  value,
  mono,
  tone,
}: {
  label: string;
  value: string;
  mono?: boolean;
  tone?: "danger" | "signal";
}) {
  const valueColor = tone === "danger" ? "text-danger" : tone === "signal" ? "text-signal" : "text-paper";
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate">{label}</span>
      <span className={`${mono ? "font-mono text-xs" : ""} ${valueColor}`}>{value}</span>
    </div>
  );
}
