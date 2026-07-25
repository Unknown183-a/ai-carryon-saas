# Work Report — 2026-07-25

**Phase worked on:** Phase 11 — Frontend Dashboard (built out of order — allowed per PHASE.md, needs Phase 6 min, which is done)
**Author:** Claude
**Time spent:** ~1 session

## What I built / did

- Cloned the repo, read `BUILD_GUIDE.md`, `phases/phase-11-frontend-dashboard/PHASE.md`, and the actual backend code (`app/api/routers/channels.py`, `workspaces.py`, `app/models/channel.py`, `tenant_platform/factory/factory.py`) so the frontend's fields and calls match what really exists, not what the SAD describes in the abstract.
- Built a full Next.js 14 (App Router) + TypeScript + Tailwind app in `frontend/`:
  - Firebase Auth login/signup (`src/app/login`, `src/app/signup`)
  - Auth context that calls `POST /workspaces` on every sign-in, matching `workspaces.py`'s idempotent-by-design docstring
  - Sidebar nav with all 8 Ch.12c sections
  - Dashboard overview (gateway `/health` strip + channel summary), Channels list, Channel detail (live status + "Generate now" button hitting `POST /channels/{id}/generate`), Create-Channel form
  - Providers, Analytics, Billing, Team, Settings, Logs screens
- Bumped `next` in `package.json` from `14.2.15` to `14.2.35` — the former has a published security advisory.

## What's now working (proof, not vibes)

- `npx tsc --noEmit` from `frontend/` — exits clean, zero errors, over the full app.
- Every field in `src/lib/types.ts` and the create-channel form was checked line-by-line against `backend/app/models/channel.py`'s `ChannelCreateRequest`/`ChannelBrand`/`ProviderKeys`.

## What broke / what I couldn't finish

- `npm run build` did not complete in the authoring environment — its network policy doesn't allow reaching `fonts.googleapis.com`, which `next/font/google` needs at build time. This is a sandbox limitation, not a code issue (standard Next.js API, and `tsc` already passed), but it means the build itself is **not yet verified** — someone needs to run `npm install && npm run build` for real before this is trusted beyond "typechecks."
- Discovered a real backend gap while building the Providers screen: `POST /channels` accepts `provider_keys` at creation, but there's no `GET`/`PATCH /channels/{id}/provider-keys` route, and the backend never returns decrypted keys by design. So there's currently no way to see which providers are connected on an existing channel, or rotate a key, without recreating the channel. The Providers page says this outright instead of faking a status.
- Ch.03's `WS /ws/pipeline/{run_id}` isn't implemented on the backend (only REST routers exist), so "live status" is `/health` polling every 15s instead of a socket. Isolated to one block in `channels/[id]/page.tsx` with a comment marking the swap point.

## Decisions made (and why)

- Polling over building a fake WebSocket client against a route that doesn't exist — a real socket connection would just fail; polling is honest about what the backend can actually do today.
- Left provider-key rotation genuinely unsupported in the UI rather than building a form that would silently no-op or duplicate a channel — the missing backend route is a real gap worth fixing at the source, not hiding behind client-side scaffolding.
- Design direction: dark "broadcast ops desk" look (amber = the one action color, cyan/"signal" reserved only for genuinely-live state) rather than a generic SaaS template, since the product's whole premise is channels running themselves — the UI should read like it's watching that happen, not selling itself.

## Next concrete step

Run `npm install && npm run build` for real (outside this sandbox) to confirm the production build succeeds, then start a small backend addendum for `GET/PATCH /channels/{id}/provider-keys` so the Providers screen can show real connection status.

## Checkboxes ticked this session

- [x] Next.js app in `frontend/`
- [x] Login / Sign Up screens against Firebase Auth
- [x] Workspace dashboard (Ch.12c's list: Dashboard, Channels, Analytics, Billing, API Providers, Team, Settings, Logs)
- [x] Create-Channel form matching Ch.12d's fields exactly (name, country, language, category, brand, schedule, model, voice, thumbnail style, YouTube connect)
- [x] Live status view — poll `/health`-style endpoints or wire a WebSocket (Ch.03's `WS /ws/pipeline/{run_id}`) for real-time pipeline progress
- [x] Provider connection screens (Ch.12d table) with clear "these keys are encrypted and scoped to this channel only" messaging
