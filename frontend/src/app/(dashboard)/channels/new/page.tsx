"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { Channel, ChannelCreateRequest } from "@/lib/types";

const EMPTY_FORM: ChannelCreateRequest = {
  name: "",
  youtube_handle: "",
  country: "US",
  language: "en",
  category: "",
  brand: { tagline: "", tone: "", logo_position: "bottom_right" },
  format: "shorts",
  target_audience: "",
  upload_schedule: "1_per_day",
  preferred_model: "",
  voice_profile: "",
  thumbnail_style: "",
  provider_keys: {},
};

export default function NewChannelPage() {
  const router = useRouter();
  const [form, setForm] = useState<ChannelCreateRequest>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof ChannelCreateRequest>(key: K, value: ChannelCreateRequest[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function updateBrand<K extends keyof ChannelCreateRequest["brand"]>(
    key: K,
    value: ChannelCreateRequest["brand"][K]
  ) {
    setForm((f) => ({ ...f, brand: { ...f.brand, [key]: value } }));
  }

  function updateProviderKey<K extends keyof ChannelCreateRequest["provider_keys"]>(
    key: K,
    value: string
  ) {
    setForm((f) => ({
      ...f,
      provider_keys: { ...f.provider_keys, [key]: value || undefined },
    }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      // Strip empty-string optionals so the backend gets `null`/omitted
      // rather than "" for fields that are meant to be optional.
      const payload: ChannelCreateRequest = {
        ...form,
        youtube_handle: form.youtube_handle || undefined,
        target_audience: form.target_audience || undefined,
        preferred_model: form.preferred_model || undefined,
        voice_profile: form.voice_profile || undefined,
        thumbnail_style: form.thumbnail_style || undefined,
      };
      const channel = await apiFetch<Channel>("/channels", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      router.replace(`/channels/view?id=${channel.channel_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create channel.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <header className="mb-8">
        <h1 className="font-display text-2xl font-semibold text-paper">New channel</h1>
        <p className="mt-1 text-sm text-slate">
          This runs through the Channel Factory — isolated Redis and Qdrant namespaces,
          its own encrypted provider keys, its own DNA.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-8">
        <Section title="Identity">
          <Field label="Channel name" required>
            <input
              className="field-input"
              required
              value={form.name}
              onChange={(e) => update("name", e.target.value)}
              placeholder="Late Night Cricket Recaps"
            />
          </Field>
          <Field label="Category" required>
            <input
              className="field-input"
              required
              value={form.category}
              onChange={(e) => update("category", e.target.value)}
              placeholder="sports, finance, tech news…"
            />
          </Field>
          <Field label="YouTube handle">
            <input
              className="field-input"
              value={form.youtube_handle}
              onChange={(e) => update("youtube_handle", e.target.value)}
              placeholder="@yourhandle"
            />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Country">
              <input
                className="field-input"
                value={form.country}
                onChange={(e) => update("country", e.target.value)}
              />
            </Field>
            <Field label="Language">
              <input
                className="field-input"
                value={form.language}
                onChange={(e) => update("language", e.target.value)}
              />
            </Field>
          </div>
          <Field label="Format">
            <select
              className="field-input"
              value={form.format}
              onChange={(e) => update("format", e.target.value as ChannelCreateRequest["format"])}
            >
              <option value="shorts">Shorts</option>
              <option value="long_form">Long form</option>
            </select>
          </Field>
          <Field label="Target audience">
            <input
              className="field-input"
              value={form.target_audience}
              onChange={(e) => update("target_audience", e.target.value)}
              placeholder="18–34, sports fans, mobile-first…"
            />
          </Field>
        </Section>

        <Section title="Brand">
          <Field label="Tagline">
            <input
              className="field-input"
              value={form.brand.tagline}
              onChange={(e) => updateBrand("tagline", e.target.value)}
            />
          </Field>
          <Field label="Tone">
            <input
              className="field-input"
              value={form.brand.tone}
              onChange={(e) => updateBrand("tone", e.target.value)}
              placeholder="energetic, deadpan, warm…"
            />
          </Field>
          <Field label="Logo position">
            <select
              className="field-input"
              value={form.brand.logo_position}
              onChange={(e) =>
                updateBrand("logo_position", e.target.value as ChannelCreateRequest["brand"]["logo_position"])
              }
            >
              <option value="top_left">Top left</option>
              <option value="top_right">Top right</option>
              <option value="bottom_left">Bottom left</option>
              <option value="bottom_right">Bottom right</option>
            </select>
          </Field>
        </Section>

        <Section title="Production">
          <Field label="Upload schedule">
            <select
              className="field-input"
              value={form.upload_schedule}
              onChange={(e) => update("upload_schedule", e.target.value)}
            >
              <option value="1_per_day">Once a day</option>
              <option value="2_per_day">Twice a day</option>
              <option value="3_per_week">Three times a week</option>
              <option value="1_per_week">Once a week</option>
            </select>
          </Field>
          <Field label="Preferred model">
            <input
              className="field-input"
              value={form.preferred_model}
              onChange={(e) => update("preferred_model", e.target.value)}
              placeholder="Leave blank for platform default"
            />
          </Field>
          <Field label="Voice profile">
            <input
              className="field-input"
              value={form.voice_profile}
              onChange={(e) => update("voice_profile", e.target.value)}
              placeholder="ElevenLabs voice ID or name"
            />
          </Field>
          <Field label="Thumbnail style">
            <input
              className="field-input"
              value={form.thumbnail_style}
              onChange={(e) => update("thumbnail_style", e.target.value)}
              placeholder="bold text, high contrast, face close-up…"
            />
          </Field>
        </Section>

        <Section
          title="Provider connections"
          note="Every key here is encrypted before it's stored, and scoped to this channel only — no other channel, even in your own workspace, can read it. All optional: leave blank and the platform default is used where one exists."
        >
          <Field label="Gemini API key">
            <input
              type="password"
              className="field-input"
              onChange={(e) => updateProviderKey("gemini_api_key", e.target.value)}
              placeholder="Falls back to platform default"
            />
          </Field>
          <Field label="Groq API key">
            <input
              type="password"
              className="field-input"
              onChange={(e) => updateProviderKey("groq_api_key", e.target.value)}
            />
          </Field>
          <Field label="OpenAI API key">
            <input
              type="password"
              className="field-input"
              onChange={(e) => updateProviderKey("openai_api_key", e.target.value)}
            />
          </Field>
          <Field label="ElevenLabs API key">
            <input
              type="password"
              className="field-input"
              onChange={(e) => updateProviderKey("elevenlabs_api_key", e.target.value)}
            />
          </Field>
          <Field label="Pexels API key">
            <input
              type="password"
              className="field-input"
              onChange={(e) => updateProviderKey("pexels_api_key", e.target.value)}
              placeholder="Background video clips for rendering — falls back to platform default"
            />
          </Field>
          <Field label="YouTube OAuth token">
            <input
              type="password"
              className="field-input"
              onChange={(e) => updateProviderKey("youtube_oauth_token", e.target.value)}
              placeholder="Connect via OAuth from the Providers page instead, if preferred"
            />
          </Field>
          <Field label="Google Cloud project">
            <input
              className="field-input"
              onChange={(e) => updateProviderKey("google_cloud_project", e.target.value)}
            />
          </Field>
          <Field label="Firebase storage bucket">
            <input
              className="field-input"
              onChange={(e) => updateProviderKey("firebase_storage_bucket", e.target.value)}
            />
          </Field>
        </Section>

        {error && (
          <p className="rounded-md border border-danger/30 bg-dangerDim px-4 py-3 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="flex items-center gap-3">
          <button type="submit" disabled={submitting} className="btn-primary">
            {submitting ? "Creating…" : "Create channel"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => router.back()}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="panel p-6">
      <h2 className="font-display text-sm font-semibold text-paper">{title}</h2>
      {note && <p className="mt-1.5 text-xs leading-relaxed text-slate">{note}</p>}
      <div className="mt-5 space-y-4">{children}</div>
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="field-label">
        {label}
        {required && <span className="ml-1 text-amber">*</span>}
      </label>
      {children}
    </div>
  );
}
