"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, fetchHealth } from "@/lib/api";
import type { Channel, GenerateRunResult } from "@/lib/types";
import StatusDot from "@/components/StatusDot";

// Ch.03 describes WS /ws/pipeline/{run_id} for real-time progress, but
// that endpoint isn't built yet (no websocket router in app/api — only
// REST). Until it exists, this polls /health as the live signal and
// treats a run as a single blocking call, per what POST
// /channels/{id}/generate actually does today. Swap the polling block
// below for a `new WebSocket(...)` connection once Ch.03's route ships —
// nothing else on this page needs to change.
const POLL_INTERVAL_MS = 15_000;

export default function ChannelDetailPage({ params }: { params: { id: string } }) {
  const [channel, setChannel] = useState<Channel | null>(null);
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
      if (!found) setError("This channel wasn't found in your workspace.");
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
