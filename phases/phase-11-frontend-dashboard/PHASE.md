<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 11 — Frontend Dashboard
*(SAD reference: Chapter 03's frontend layer, Chapters 00/0.5 — Customer Journey)*

**Goal:** a customer can sign up, connect providers, create a channel, and watch it run — without touching the API directly.

**Depends on:** Phase 6 at minimum (needs working multi-tenant backend); ideally Phase 10 too, so status shown is real.

**Tasks:**
- [x] Next.js app in `frontend/`
- [x] Login / Sign Up screens against Firebase Auth
- [x] Workspace dashboard (Ch.12c's list: Dashboard, Channels, Analytics, Billing, API Providers, Team, Settings, Logs)
- [x] Create-Channel form matching Ch.12d's fields exactly (name, country, language, category, brand, schedule, model, voice, thumbnail style, YouTube connect)
- [x] Live status view — poll `/health`-style endpoints or wire a WebSocket (Ch.03's `WS /ws/pipeline/{run_id}`) for real-time pipeline progress
- [x] Provider connection screens (Ch.12d table) with clear "these keys are encrypted and scoped to this channel only" messaging

**Definition of Done:** a brand-new user, using only the UI, can go from signup to a channel with `status: ready`, matching the fig 0.1 journey exactly.

**Handoff Notes:**
> Built the full Next.js 14 / TypeScript / Tailwind app in `frontend/`. `npx tsc --noEmit` passes clean (zero errors). `npm run build` could **not** be run to completion in the build sandbox because `next/font/google` needs `fonts.googleapis.com`, which wasn't reachable there — this is a sandbox network-policy limitation, not a code issue, and it's standard Next.js usage that will build fine with normal internet access. Whoever picks this up next: run `npm run build` once for real before calling it fully verified, since only the typecheck (not the build) was confirmed here.
>
> Real gap found while wiring the Providers screen, not a frontend bug: `POST /channels` accepts `provider_keys` at creation, but there's no `GET`/`PATCH /channels/{id}/provider-keys` route, and by design the backend never returns decrypted keys. So today a user can't see which providers are connected on an existing channel or rotate a key without recreating the channel. The Providers page (`src/app/(dashboard)/providers/page.tsx`) says this outright rather than faking a status. Worth a small backend follow-up (probably its own phase or a Phase 6 addendum) to add that route.
>
> Live status view polls `/health` every 15s rather than using a WebSocket — Ch.03's `WS /ws/pipeline/{run_id}` isn't implemented on the backend (only REST routers exist in `app/api/routers/`). The polling code is isolated in `channels/[id]/page.tsx` with a comment marking exactly where to swap in a real socket once that route exists; nothing else on the page needs to change.
>
> Ran ahead of Phase 10 on purpose (workspace only has Phase 6 done, plus Phase 7 done and Phase 8/9 in progress per `STATUS.md`) — PHASE.md explicitly allows this ("Depends on: Phase 6 at minimum ... ideally Phase 10 too"). Consequence: the "Live status" panel only has the gateway's plain `/health` to poll, not the richer Health Agent data Phase 10 will eventually produce. Nothing here should need restructuring once Phase 10 lands — it's a data-source swap, not an architecture change.
>
> Also bumped `next` from `14.2.15` (has a known security advisory) to `14.2.35` in `package.json` before anyone installs from this.

---
