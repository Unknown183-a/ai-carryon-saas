<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 11 — Frontend Dashboard
*(SAD reference: Chapter 03's frontend layer, Chapters 00/0.5 — Customer Journey)*

**Goal:** a customer can sign up, connect providers, create a channel, and watch it run — without touching the API directly.

**Depends on:** Phase 6 at minimum (needs working multi-tenant backend); ideally Phase 10 too, so status shown is real.

**Tasks:**
- [ ] Next.js app in `frontend/`
- [ ] Login / Sign Up screens against Firebase Auth
- [ ] Workspace dashboard (Ch.12c's list: Dashboard, Channels, Analytics, Billing, API Providers, Team, Settings, Logs)
- [ ] Create-Channel form matching Ch.12d's fields exactly (name, country, language, category, brand, schedule, model, voice, thumbnail style, YouTube connect)
- [ ] Live status view — poll `/health`-style endpoints or wire a WebSocket (Ch.03's `WS /ws/pipeline/{run_id}`) for real-time pipeline progress
- [ ] Provider connection screens (Ch.12d table) with clear "these keys are encrypted and scoped to this channel only" messaging

**Definition of Done:** a brand-new user, using only the UI, can go from signup to a channel with `status: ready`, matching the fig 0.1 journey exactly.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---
