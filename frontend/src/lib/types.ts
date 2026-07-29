/**
 * Mirrors backend/app/models/channel.py exactly — field-for-field, so the
 * Create-Channel form and the JSON it sends never drift from what the
 * Channel Factory (Ch.12d) actually accepts.
 */

export type ChannelBrand = {
  tagline: string;
  tone: string;
  logo_position: "top_left" | "top_right" | "bottom_left" | "bottom_right";
};

export type ProviderKeys = {
  youtube_oauth_token?: string;
  gemini_api_key?: string;
  groq_api_key?: string;
  openai_api_key?: string;
  elevenlabs_api_key?: string;
  pexels_api_key?: string;
  google_cloud_project?: string;
  firebase_storage_bucket?: string;
};

export type ChannelCreateRequest = {
  name: string;
  youtube_handle?: string;
  country: string;
  language: string;
  category: string;
  brand: ChannelBrand;
  format: "shorts" | "long_form";
  target_audience?: string;
  upload_schedule: string;
  preferred_model?: string;
  voice_profile?: string;
  thumbnail_style?: string;
  provider_keys: ProviderKeys;
};

/** Mirrors backend/app/models/channel.py's ProviderKeyStatus — booleans
 * only, since the backend never returns a decrypted key value. */
export type ProviderKeyStatus = {
  youtube_oauth_token: boolean;
  gemini_api_key: boolean;
  groq_api_key: boolean;
  openai_api_key: boolean;
  elevenlabs_api_key: boolean;
  pexels_api_key: boolean;
  google_cloud_project: boolean;
  firebase_storage_bucket: boolean;
};

export type Channel = {
  channel_id: string;
  workspace_id: string;
  owner_uid: string;
  status: "configuring" | "ready" | "paused" | "error" | string;
  name: string;
  youtube_handle?: string | null;
  country: string;
  language: string;
  category: string;
  brand: ChannelBrand;
  format: string;
  target_audience?: string | null;
  upload_schedule: string;
  preferred_model: string;
  voice_profile?: string | null;
  thumbnail_style?: string | null;
};

/** One entry from GET /channels/{id}/runs — mirrors what
 * `record_run` persists in Firestore's `channel_runs` collection. */
export type RunSummary = {
  run_id: string;
  channel_id: string;
  created_at: string;
  triggered_by_uid?: string;
  status?: string; // "reviewed" | "failed" | "error" | string
  topic?: string;
  review_verdict?: "pass" | "fail" | string;
  failure_reason?: string | null;
  render_task_id?: string | null;
  render_status?: string | null; // "enqueued" | "completed" | "failed" | string
  render_failure_reason?: string | null;
  youtube_video_id?: string | null;
  run_log: string[];
};

export type GenerateRunResult = {
  run_id: string;
  status?: string;
  topic?: string;
  script?: unknown;
  seo?: unknown;
  thumbnail_brief?: unknown;
  hook?: unknown;
  tags?: unknown;
  description?: unknown;
  review_verdict?: "pass" | "fail" | string;
  review_findings?: unknown;
  failure_reason?: string | null;
  render_task_id?: string | null;
  render_status?: string | null;
  render_failure_reason?: string | null;
};
