<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 6 — Multi-Tenancy: Channel Brain, Workspace, Channel Factory
*(SAD reference: Chapters 12b–12e — Channel Brain, User Workspace, API Providers, Tenant Isolation)*

**Goal:** the single hardcoded channel from Phase 4 becomes N database-driven channels, each isolated, created through a real onboarding flow.

**Depends on:** Phase 5 (needs Qdrant collections to namespace) and Phase 3 (needs Redis to namespace).

**Tasks:**
- [ ] Retrofit Redis keys everywhere to `ch:{channel_id}:*` prefix (Ch.12b) — grep the whole codebase for raw Redis calls, there should be none left unprefixed
- [ ] Retrofit every Qdrant write/query to carry mandatory `channel_id` metadata filter (Ch.12b)
- [ ] `backend/platform/channel_factory/brain.py` — the Channel Brain model (DNA, prompt library overrides, per-channel settings)
- [ ] `backend/platform/channel_factory/factory.py` — implements the exact sequence from fig 12d.1: Validate Configuration → Create Firestore Record → Create Redis Namespace → Create Qdrant Namespace → Generate Channel DNA → Channel Ready
- [ ] `POST /workspaces` — creates a Workspace document on first login (Ch.12c)
- [ ] `POST /channels` (replace the raw Phase 2 version) — now runs through the Channel Factory
- [ ] Provider-key storage: encrypt at rest, store per channel, scoped so one channel's agents never see another channel's keys (Ch.12d table)
- [ ] Permission Check middleware: Workspace ID → Channel ID → Authenticated User ID → Permission Check, in that order (Ch.12e) — wire into every router, not just channels
- [ ] Write a negative test: User A's token requesting User B's channel must be rejected at the middleware layer, before touching LangGraph

**Definition of Done:** two different Firebase users can each create a channel, run the Phase 4 pipeline against their own channel independently, and neither can read, list, or trigger the other's channel — verified by an automated test, not manual inspection.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---
