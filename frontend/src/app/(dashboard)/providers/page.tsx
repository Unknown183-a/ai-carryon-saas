"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { Channel } from "@/lib/types";

const PROVIDER_LABELS: Record<string, string> = {
  gemini_api_key: "Gemini",
  groq_api_key: "Groq",
  openai_api_key: "OpenAI",
  elevenlabs_api_key: "ElevenLabs",
  youtube_oauth_token: "YouTube",
  google_cloud_project: "Google Cloud",
  firebase_storage_bucket: "Firebase Storage",
};

export default function ProvidersPage() {
  const [channels, setChannels] = useState<Channel[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Channel[]>("/channels")
      .then(setChannels)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load channels."));
  }, []);

  return (
    <div className="max-w-3xl">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-paper">API Providers</h1>
        <p className="mt-1 text-sm text-slate">
          Every key is encrypted at rest and scoped to the single channel it's attached to —
          no other channel, even in this workspace, can read it.
        </p>
      </header>

      <div className="panel mb-6 border-amberDim bg-amberDim/40 p-4">
        <p className="text-sm text-amber">
          Known gap: the gateway currently only <em>accepts</em> provider keys at channel
          creation (<code className="font-mono text-xs">POST /channels</code>). There's no
          endpoint yet to view which keys are set or update them afterward — the backend
          intentionally never returns decrypted keys, and no
          <code className="font-mono text-xs"> GET/PATCH /channels/&#123;id&#125;/provider-keys</code>{" "}
          route exists. So this page can list channels, but can't yet show connection status
          or let you rotate a key without recreating the channel.
        </p>
      </div>

      {error && (
        <p className="mb-6 rounded-md border border-danger/30 bg-dangerDim px-4 py-3 text-sm text-danger">
          {error}
        </p>
      )}

      {channels === null && !error && <p className="text-sm text-slate">Loading channels…</p>}

      {channels !== null && channels.length === 0 && (
        <div className="panel border-dashed px-6 py-10 text-center">
          <p className="text-sm text-paper">No channels yet.</p>
          <p className="mt-1 text-sm text-slate">Provider keys are set per channel, when you create it.</p>
          <Link href="/channels/new" className="btn-primary mt-4 inline-flex">
            + New channel
          </Link>
        </div>
      )}

      {channels !== null && channels.length > 0 && (
        <div className="panel divide-y divide-line">
          {channels.map((c) => (
            <div key={c.channel_id} className="flex items-center justify-between px-5 py-4">
              <div>
                <p className="font-medium text-paper">{c.name}</p>
                <p className="mt-0.5 font-mono text-xs text-slate">{c.channel_id}</p>
              </div>
              <span className="text-xs text-slate">
                Set at creation — see{" "}
                <Link href={`/channels/${c.channel_id}`} className="text-signal hover:underline">
                  channel detail
                </Link>
              </span>
            </div>
          ))}
        </div>
      )}

      <p className="mt-6 text-xs text-slate">
        Providers this platform integrates with:{" "}
        {Object.values(PROVIDER_LABELS).join(", ")}.
      </p>
    </div>
  );
}
