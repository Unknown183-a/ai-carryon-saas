"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { Channel } from "@/lib/types";
import StatusDot from "@/components/StatusDot";

export default function ChannelsPage() {
  const [channels, setChannels] = useState<Channel[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Channel[]>("/channels")
      .then(setChannels)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load channels."));
  }, []);

  return (
    <div className="max-w-5xl">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-paper">Channels</h1>
          <p className="mt-1 text-sm text-slate">Every channel your workspace runs.</p>
        </div>
        <Link href="/channels/new" className="btn-primary">
          + New channel
        </Link>
      </header>

      {error && (
        <p className="mb-6 rounded-md border border-danger/30 bg-dangerDim px-4 py-3 text-sm text-danger">
          {error}
        </p>
      )}

      {channels === null && !error && <p className="text-sm text-slate">Loading channels…</p>}

      {channels !== null && channels.length === 0 && (
        <div className="panel border-dashed px-6 py-14 text-center">
          <p className="text-sm text-paper">No channels yet.</p>
          <p className="mt-1 text-sm text-slate">
            Create your first one — it'll handle trend research, scripting, review, and
            (once Phase 7/8 are wired up) rendering and scheduling on its own.
          </p>
          <Link href="/channels/new" className="btn-primary mt-4 inline-flex">
            + New channel
          </Link>
        </div>
      )}

      {channels !== null && channels.length > 0 && (
        <div className="panel divide-y divide-line">
          {channels.map((c) => (
            <Link
              key={c.channel_id}
              href={`/channels/${c.channel_id}`}
              className="flex items-center justify-between px-5 py-4 transition hover:bg-panel2"
            >
              <div>
                <p className="font-medium text-paper">{c.name}</p>
                <p className="mt-0.5 text-xs text-slate">
                  {c.category} · {c.language.toUpperCase()}/{c.country} · {c.upload_schedule.replace(/_/g, " ")}
                </p>
              </div>
              <StatusDot status={c.status} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
