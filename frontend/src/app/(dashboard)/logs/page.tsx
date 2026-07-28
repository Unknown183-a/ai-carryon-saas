"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { Channel, RunSummary } from "@/lib/types";

const STATUS_STYLE: Record<string, string> = {
  reviewed: "text-signal",
  failed: "text-danger",
  error: "text-danger",
};

export default function LogsPage() {
  const [channels, setChannels] = useState<Channel[] | null>(null);
  const [channelError, setChannelError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Channel[]>("/channels")
      .then((cs) => {
        setChannels(cs);
        if (cs.length > 0) setSelectedId(cs[0].channel_id);
      })
      .catch((err) => setChannelError(err instanceof Error ? err.message : "Could not load channels."));
  }, []);

  return (
    <div className="max-w-3xl">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-paper">Logs</h1>
        <p className="mt-1 text-sm text-slate">
          Every finished pipeline run per channel — trend, research, planning, the six
          parallel writers, and review, in the order they executed.
        </p>
      </header>

      {channelError && (
        <p className="mb-6 rounded-md border border-danger/30 bg-dangerDim px-4 py-3 text-sm text-danger">
          {channelError}
        </p>
      )}

      {channels === null && !channelError && <p className="text-sm text-slate">Loading channels…</p>}

      {channels !== null && channels.length === 0 && (
        <div className="panel border-dashed px-6 py-10 text-center">
          <p className="text-sm text-paper">No channels yet.</p>
          <p className="mt-1 text-sm text-slate">Runs are logged per channel, once one exists.</p>
          <Link href="/channels/new" className="btn-primary mt-4 inline-flex">
            + New channel
          </Link>
        </div>
      )}

      {channels !== null && channels.length > 0 && selectedId && (
        <>
          <div className="mb-6 flex flex-wrap gap-2">
            {channels.map((c) => (
              <button
                key={c.channel_id}
                onClick={() => setSelectedId(c.channel_id)}
                className={`rounded-md border px-3 py-1.5 text-sm ${
                  selectedId === c.channel_id
                    ? "border-signal text-signal"
                    : "border-line text-slate hover:text-paper"
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>

          <ChannelRunLog channelId={selectedId} />
        </>
      )}
    </div>
  );
}

function ChannelRunLog({ channelId }: { channelId: string }) {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(() => {
    setRuns(null);
    apiFetch<RunSummary[]>(`/channels/${channelId}/runs`)
      .then(setRuns)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load runs."));
  }, [channelId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return <p className="rounded-md border border-danger/30 bg-dangerDim px-4 py-3 text-sm text-danger">{error}</p>;
  }

  if (runs === null) {
    return <p className="text-sm text-slate">Loading runs…</p>;
  }

  if (runs.length === 0) {
    return (
      <div className="panel border-dashed px-6 py-10 text-center">
        <p className="text-sm text-paper">No runs yet for this channel.</p>
        <p className="mt-1 text-sm text-slate">
          Trigger a run from the channel's page — every attempt, pass or fail, shows up here
          once it finishes.
        </p>
      </div>
    );
  }

  return (
    <div className="panel divide-y divide-line">
      {runs.map((run) => {
        const isOpen = expanded === run.run_id;
        const statusColor = STATUS_STYLE[run.status ?? ""] ?? "text-slate";
        return (
          <div key={run.run_id} className="px-5 py-4">
            <button
              onClick={() => setExpanded(isOpen ? null : run.run_id)}
              className="flex w-full items-center justify-between text-left"
            >
              <div>
                <p className="font-medium text-paper">{run.topic || "(no topic recorded)"}</p>
                <p className="mt-0.5 text-xs text-slate">
                  {new Date(run.created_at).toLocaleString()} · <span className="font-mono">{run.run_id}</span>
                </p>
              </div>
              <span className={`text-xs font-medium ${statusColor}`}>{run.status ?? "unknown"}</span>
            </button>

            {isOpen && (
              <div className="mt-3 space-y-3 border-t border-line pt-3">
                {run.review_verdict && (
                  <Row label="Review verdict" value={run.review_verdict} />
                )}
                {run.failure_reason && <Row label="Failure reason" value={run.failure_reason} tone="danger" />}
                {run.render_status && <Row label="Render status" value={run.render_status} />}
                {run.render_task_id && <Row label="Render task" value={run.render_task_id} mono />}
                {run.render_failure_reason && (
                  <Row label="Render failure reason" value={run.render_failure_reason} tone="danger" />
                )}
                {run.youtube_video_id && (
                  <Row
                    label="YouTube video"
                    value={`https://youtube.com/watch?v=${run.youtube_video_id}`}
                  />
                )}

                <div>
                  <p className="mb-1.5 text-xs uppercase tracking-wide text-slate">Node-by-node log</p>
                  <ol className="space-y-1">
                    {run.run_log.map((entry, i) => (
                      <li key={i} className="font-mono text-xs text-slate">
                        {String(i + 1).padStart(2, "0")}. {entry}
                      </li>
                    ))}
                  </ol>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function Row({ label, value, mono, tone }: { label: string; value: string; mono?: boolean; tone?: "danger" }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate">{label}</span>
      <span className={`${mono ? "font-mono text-xs" : ""} ${tone === "danger" ? "text-danger" : "text-paper"}`}>
        {value}
      </span>
    </div>
  );
}
