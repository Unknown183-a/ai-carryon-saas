"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, fetchHealth } from "@/lib/api";
import type { Channel } from "@/lib/types";
import StatusDot from "@/components/StatusDot";

export default function DashboardOverviewPage() {
  const [health, setHealth] = useState<"checking" | "ok" | "unreachable">("checking");
  const [channels, setChannels] = useState<Channel[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(() => setHealth("ok"))
      .catch(() => setHealth("unreachable"));

    apiFetch<Channel[]>("/channels")
      .then(setChannels)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load channels."));
  }, []);

  const ready = channels?.filter((c) => c.status === "ready").length ?? 0;
  const configuring = channels?.filter((c) => c.status === "configuring").length ?? 0;
  const total = channels?.length ?? 0;

  return (
    <div className="max-w-5xl">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-paper">Mission Control</h1>
          <p className="mt-1 text-sm text-slate">Everything your channels are doing, at a glance.</p>
        </div>
        <div className="panel flex items-center gap-2 px-3 py-2">
          <StatusDot status={health === "checking" ? "configuring" : health} />
          <span className="text-xs text-slate">Gateway</span>
        </div>
      </header>

      {error && (
        <p className="mb-6 rounded-md border border-danger/30 bg-dangerDim px-4 py-3 text-sm text-danger">
          {error}
        </p>
      )}

      <div className="mb-8 grid grid-cols-3 gap-4">
        <StatCard label="Channels" value={total} />
        <StatCard label="Ready" value={ready} accent="signal" />
        <StatCard label="Configuring" value={configuring} accent="amber" />
      </div>

      <div className="panel p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-sm font-semibold text-paper">Channels</h2>
          <Link href="/channels/new" className="btn-primary text-xs">
            + New channel
          </Link>
        </div>

        {channels === null && !error && (
          <p className="text-sm text-slate">Loading channels…</p>
        )}

        {channels !== null && channels.length === 0 && (
          <EmptyState />
        )}

        {channels !== null && channels.length > 0 && (
          <ul className="divide-y divide-line">
            {channels.slice(0, 6).map((c) => (
              <li key={c.channel_id} className="flex items-center justify-between py-3">
                <div>
                  <Link
                    href={`/channels/view?id=${c.channel_id}`}
                    className="font-medium text-paper hover:text-signal"
                  >
                    {c.name}
                  </Link>
                  <p className="font-mono text-xs text-slate">{c.channel_id}</p>
                </div>
                <StatusDot status={c.status} />
              </li>
            ))}
          </ul>
        )}

        {channels !== null && channels.length > 6 && (
          <Link href="/channels" className="mt-3 inline-block text-xs text-signal hover:underline">
            View all {channels.length} channels →
          </Link>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: "signal" | "amber";
}) {
  const valueColor =
    accent === "signal" ? "text-signal" : accent === "amber" ? "text-amber" : "text-paper";
  return (
    <div className="panel p-5">
      <p className="text-xs uppercase tracking-wide text-slate">{label}</p>
      <p className={`mt-2 font-display text-3xl font-semibold ${valueColor}`}>{value}</p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-md border border-dashed border-line px-6 py-10 text-center">
      <p className="text-sm text-paper">No channels yet.</p>
      <p className="mt-1 text-sm text-slate">Set one up and it'll start generating on its own.</p>
      <Link href="/channels/new" className="btn-primary mt-4 inline-flex">
        + New channel
      </Link>
    </div>
  );
}
