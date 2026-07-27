"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "@/lib/api";
import type { Channel, ProviderKeyStatus } from "@/lib/types";

const PROVIDER_LABELS: Record<keyof ProviderKeyStatus, string> = {
  gemini_api_key: "Gemini",
  groq_api_key: "Groq",
  openai_api_key: "OpenAI",
  elevenlabs_api_key: "ElevenLabs",
  pexels_api_key: "Pexels",
  youtube_oauth_token: "YouTube",
  google_cloud_project: "Google Cloud",
  firebase_storage_bucket: "Firebase Storage",
};

const PROVIDER_FIELDS = Object.keys(PROVIDER_LABELS) as (keyof ProviderKeyStatus)[];

export default function ProvidersPage() {
  const [channels, setChannels] = useState<Channel[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

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
          Every key is encrypted at rest and scoped to the single channel it&apos;s attached to —
          no other channel, even in this workspace, can read it.
        </p>
      </header>

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
        <div className="space-y-3">
          {channels.map((c) => (
            <ChannelProviderRow
              key={c.channel_id}
              channel={c}
              open={expanded === c.channel_id}
              onToggle={() => setExpanded((cur) => (cur === c.channel_id ? null : c.channel_id))}
            />
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

function ChannelProviderRow({
  channel,
  open,
  onToggle,
}: {
  channel: Channel;
  open: boolean;
  onToggle: () => void;
}) {
  const [status, setStatus] = useState<ProviderKeyStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || status !== null || loadError !== null) return;
    apiFetch<ProviderKeyStatus>(`/channels/${channel.channel_id}/provider-keys`)
      .then(setStatus)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Could not load key status."));
  }, [open, channel.channel_id, status, loadError]);

  return (
    <div className="panel">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <div>
          <p className="font-medium text-paper">{channel.name}</p>
          <p className="mt-0.5 font-mono text-xs text-slate">{channel.channel_id}</p>
        </div>
        <span className="text-xs text-signal">{open ? "Hide" : "Manage keys"}</span>
      </button>

      {open && (
        <div className="border-t border-line px-5 py-4">
          {loadError && (
            <p className="mb-3 rounded-md border border-danger/30 bg-dangerDim px-3 py-2 text-sm text-danger">
              {loadError}
            </p>
          )}
          {status === null && !loadError && <p className="text-sm text-slate">Loading key status…</p>}
          {status !== null && (
            <div className="space-y-3">
              {PROVIDER_FIELDS.map((field) => (
                <ProviderKeyField
                  key={field}
                  channelId={channel.channel_id}
                  field={field}
                  connected={status[field]}
                  onRotated={(newStatus) => setStatus(newStatus)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ProviderKeyField({
  channelId,
  field,
  connected,
  onRotated,
}: {
  channelId: string;
  field: keyof ProviderKeyStatus;
  connected: boolean;
  onRotated: (status: ProviderKeyStatus) => void;
}) {
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  async function handleSave() {
    if (!value.trim()) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await apiFetch<ProviderKeyStatus>(`/channels/${channelId}/provider-keys`, {
        method: "PATCH",
        body: JSON.stringify({ [field]: value }),
      });
      onRotated(updated);
      setValue("");
    } catch (err) {
      setSaveError(
        err instanceof ApiError && err.status === 404
          ? "Backend doesn't have this route deployed yet."
          : err instanceof Error
            ? err.message
            : "Could not save key."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${connected ? "bg-signal" : "bg-line"}`}
        title={connected ? "Connected" : "Not set"}
      />
      <span className="w-36 shrink-0 text-sm text-paper">{PROVIDER_LABELS[field]}</span>
      <input
        type="password"
        className="field-input flex-1"
        placeholder={connected ? "Connected — enter a new value to rotate" : "Not set — paste a key to connect"}
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <button
        type="button"
        onClick={handleSave}
        disabled={saving || !value.trim()}
        className="btn-primary shrink-0 px-3 py-1.5 text-xs disabled:opacity-50"
      >
        {saving ? "Saving…" : connected ? "Rotate" : "Connect"}
      </button>
      {saveError && <span className="text-xs text-danger">{saveError}</span>}
    </div>
  );
}
