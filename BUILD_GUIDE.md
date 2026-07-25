# AI CarryON — Build Guide & Handoff Document

> **Companion to:** `docs/architecture/AI-CarryON-Architecture.html` (the SAD — read that first for *why*, use this for *what to do next*).
> **Purpose:** any developer — including one who has never seen this project — should be able to open this file, find the current phase, and continue without a handoff call.

---

## 0. How To Use This Document (read this first)

This guide is split into **13 phases (0–12)**. Phases are ordered by *dependency*, not by importance — Phase 4 cannot be built correctly before Phase 2 exists, so don't skip ahead even if a later phase feels more exciting.

Every phase has the same five sections:

| Section | What it tells the next developer |
|---|---|
| **Goal** | What "done" means for this phase, in one sentence |
| **Depends On** | Which earlier phases must already be complete |
| **Tasks** | A checklist — tick boxes as you go, commit the ticked box |
| **Definition of Done** | The concrete test that proves the phase actually works |
| **Handoff Notes** | Free text — **whoever stops mid-phase writes here before stopping** |

### The one rule for stopping mid-work

**Before you stop, for any reason, do these three things:**

1. Tick every checkbox you actually finished (don't tick "in progress" boxes).
2. Write 2–5 sentences in that phase's **Handoff Notes**: what you were doing, what broke, what you were about to try next, and any command/error worth pasting.
3. Update the **Current Status** table below with the phase, date, and your name.

If everyone who touches this project follows that rule, no handoff call is ever required.

---

## 1. Current Status

*(Update this table every time you stop working. This is the single source of truth for "where are we.")*

| Field | Value |
|---|---|
| **Active phase**           | Phase 9 — Deployment (mainline); Phase 11 — Frontend Dashboard also built, out of order on purpose |
| **Last updated by**        | Claude                                |
| **Last updated on**        | 2026-07-25                            |
| **Blocking issue, if any** | See `STATUS.md` — that file, not this table, has been the actually-maintained source of truth since around Phase 2; this table had drifted five phases behind it until now. Short version: Phase 7 (ElevenLabs/YouTube/ffmpeg) and Phase 11 (`npm run build`) both still need a real-keys/real-build pass; Phase 8's "real scheduled trigger" observation is blocked on Phase 9's deploy-target decision. |
| **Next concrete action**   | Begin Phase 9 — see `phases/phase-09-deployment/PHASE.md`. |

---

## 2. Before You Start — Accounts & Prerequisites

Get all of these set up **before Phase 0**, even though most aren't used until later phases. Doing this up front means no developer is ever blocked mid-phase waiting on account approval.

- [x] GitHub repo created (private is fine to start)
- [x] Firebase project created — [console.firebase.google.com](https://console.firebase.google.com) (Spark/free plan)
- [x] Upstash account for Redis — [upstash.com](https://upstash.com) (free tier, REST-based, no local process) *(Phase 7: also its Redis-protocol `rediss://` connection string, same instance, used as Celery's broker/backend)*
- [x] Qdrant Cloud account — [cloud.qdrant.io](https://cloud.qdrant.io) (free 1GB cluster) *(real cluster created and verified — see Phase 5's real-keys work report)*
- [x] Gemini API key — [aistudio.google.com](https://aistudio.google.com)
- [ ] (Optional, can defer) Google Cloud project for Cloud Run / Cloud Tasks / Cloud Scheduler — Phase 7 ended up NOT needing Cloud Tasks (see `docs/decisions/0001-task-queue-choice.md`); still open for Phase 9's deploy-target decision and Phase 8's cron trigger
- [ ] ElevenLabs API key for voice — *(no longer optional as of Phase 7 — `voice_worker.py` needs `ELEVENLABS_API_KEY` for real runs; runs fine in tests via the fake)*
- [ ] YouTube Data API OAuth credentials — [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services *(needed for `upload_worker.py`'s real runs — `YOUTUBE_CLIENT_SECRETS_B64` / `YOUTUBE_TOKEN_B64`)*
- [x] Groq API key — [console.groq.com](https://console.groq.com) *(this checklist predates Phase 4 — added now, per `STATUS.md`'s own note that it was missing)*
- [x] Serper.dev API key — [serper.dev](https://serper.dev) *(Research Agent's web search; same note as Groq above)*

**Local dev environment:**
- [x] Python 3.11+
- [ ] Node 20+
- [ ] Docker Desktop (only needed from Phase 9 onward — don't install if RAM-constrained until then)
- [ ] `ffmpeg` installed locally *(new as of Phase 7 — `render_worker.py` shells out to the real binary; `brew install ffmpeg` on Mac, already in `docker/Dockerfile` for the container)*

Create a `.env.example` in the repo root now, and every phase below appends to it instead of inventing new undocumented env vars:

```
# Firebase
FIREBASE_PROJECT_ID=
FIREBASE_SERVICE_ACCOUNT_JSON=

# Redis (Upstash)
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=

# Qdrant
QDRANT_URL=
QDRANT_API_KEY=

# LLM providers
GEMINI_API_KEY=
GROQ_API_KEY=
OPENAI_API_KEY=

# YouTube
YOUTUBE_CLIENT_SECRETS_B64=
YOUTUBE_TOKEN_B64=

# ElevenLabs
ELEVENLABS_API_KEY=
```

---

## Phase 0 — Repo & Skeleton
*(SAD reference: Chapter 13 — Folder Structure)*

**Goal:** an empty but correctly-shaped repo exists, so no later phase needs to restructure folders.

**Depends on:** nothing.

**Tasks:**
- [x] Run the skeleton command below
- [x] Commit with message `chore: initial folder skeleton`
- [x] Add `.env` to `.gitignore`, commit `.env.example` instead
- [x] Add a root `README.md` that just links to this file and the SAD

```bash
mkdir -p ai-carryon/{frontend,backend/{app/{api/{routers,middleware},core,services,models,database,workers},ai/{agents,langgraph,memory,rag,prompts,models,tools},platform/{channels,factory,workspace,scheduler,monitoring,security},integrations/{firebase,youtube,gemini,openai,groq},configs},deployment,tests,docs/{architecture,api,decisions,deployment,diagrams},docker,.github/workflows}
cd ai-carryon && git init && git add . && git commit -m "chore: initial folder skeleton"
```

**Definition of Done:** `tree -L 3` shows every folder from Chapter 13's tree; repo is pushed to GitHub.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---

## Phase 1 — Firebase Auth + Firestore
*(SAD reference: Chapter 12 — Firebase & Firestore)*

**Goal:** a user can be created via Firebase Auth, and a Firestore document can be written and read back, respecting security rules.

**Depends on:** Phase 0.

**Tasks:**
- [x] Enable Email/Password sign-in method in Firebase console
- [x] Create Firestore in Native mode
- [x] Create empty collections: `users`, `projects`, `channels`, `videos`, `analytics`, `schedules`, `settings` (Ch.12)
- [x] Write `firestore.rules` enforcing `request.auth.uid` membership on every read/write (Ch.12e) — **do this now, not later**
- [x] Deploy rules: `firebase deploy --only firestore:rules`
- [x] Download service account JSON, store as `FIREBASE_SERVICE_ACCOUNT_JSON` (base64-encoded) in `.env`
- [x] Write a throwaway test script that: creates a test user, writes one document to `users/{uid}`, reads it back, confirms a *different* fake uid is denied by the rules

**Definition of Done:** the throwaway test script passes, including the negative test (wrong uid is rejected).

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---

## Phase 2 — FastAPI Gateway (shell only)
*(SAD reference: Chapter 03 — FastAPI Gateway)*

**Goal:** a running FastAPI app that verifies a Firebase JWT and can read/write one Firestore document through a real endpoint — no LangGraph yet.

**Depends on:** Phase 1.

**Tasks:**
- [x] `backend/app/api/main.py` — app instance, CORS, middleware registration
- [x] `backend/app/api/middleware/auth.py` — verifies `Authorization: Bearer <jwt>` against Firebase Admin SDK
- [x] `backend/app/api/dependencies.py` — `Depends()` providers for current user + Firestore client
- [x] `backend/app/api/routers/channels.py` — `GET /channels` (list), `POST /channels` (create, no factory logic yet — just a raw Firestore write)
- [x] `GET /health` endpoint returning `{"status": "ok"}` — this is what the Health Agent (Phase 10) will poll later, build the shape now
- [x] Rate limiter middleware is a stub for now (real logic in Phase 3)

**Definition of Done:** `curl` with a valid Firebase JWT successfully creates and lists a channel document; `curl` with no token or a bad token gets `401`.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---

## Phase 3 — Redis (Upstash)
*(SAD reference: Chapter 11 — Redis)*

**Goal:** the rate limiter middleware from Phase 2 is real, backed by Redis — proving the cache-first pattern works before agents depend on it.

**Depends on:** Phase 2.

**Tasks:**
- [x] `backend/app/core/redis_client.py` — thin wrapper around Upstash REST client with `get`, `set`, `incr`, TTL support
- [x] Wire real rate limiting into `backend/app/api/middleware/rate_limit.py` using key prefix `rl:*` (Ch.11 table) and a 60-second TTL
- [x] Confirm the 429 response fires after the configured request budget is exceeded
- [x] Leave the namespacing (`ch:{channel_id}:*`) as a TODO comment — real multi-tenant namespacing happens in Phase 6, don't build it early

**Definition of Done:** hammering the `/health` endpoint past the rate limit returns `429`; waiting past the TTL resets it.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---

## Phase 4 — LangGraph, Single Hardcoded Channel
*(SAD reference: Chapters 04–08 — LangGraph, Research Agent, Planner, Parallel Generation, Review)*

**This is the highest-risk phase in the whole build — budget the most time here.**

**Goal:** one hardcoded channel runs the full graph — Trend → Research → Planner → Parallel(6) → Review — and produces a reviewed script + SEO + thumbnail brief, still without rendering or multi-tenancy.

**Depends on:** Phase 3 (agents will use Redis caching).

**Tasks:**
- [x] Install LangGraph: `pip install langgraph`
- [x] `backend/ai/langgraph/graph.py` — define the `StateGraph` with the node sequence from Ch.04's diagram
- [x] `backend/ai/langgraph/state.py` — the shared state schema (topic, research_summary, planner_json, per-agent outputs)
- [x] Built fresh (no `agents_cricket`/`agents_hindi` code existed to port):
  - [x] `backend/ai/agents/trend_agent.py` — Google Trends via pytrends, wraps Redis caching (`trend:*`, Ch.11)
  - [x] `backend/ai/agents/research_agent.py` — web search (Serper) + LLM grounding; RAG/Qdrant wiring deferred to Phase 5
  - [x] `backend/ai/agents/planner_agent.py` — outputs the JSON contract from Ch.06
  - [x] `backend/ai/agents/script_agent.py`, `seo_agent.py`, `thumbnail_agent.py`, `hook_agent.py`, `tags_agent.py`, `description_agent.py` — registered as parallel LangGraph nodes (Ch.07)
  - [x] `backend/ai/agents/review_agent.py` — grammar/fact/copyright checks in order, plus the LLM Judge step from Ch.08
- [x] Wire the conditional retry edge: Review failure routes back to the specific failing Parallel agent, capped at 3 retries (Ch.04)
- [x] `POST /channels/{id}/generate` in FastAPI calls `graph.ainvoke(state)` (Ch.03's "How FastAPI talks to LangGraph")
- [x] Hardcode one channel's config in code (no database-driven config yet)

**Definition of Done:** calling `POST /channels/{id}/generate` end-to-end produces a reviewed script + SEO + thumbnail brief in the response, and a forced Review failure demonstrably retries the correct single agent, not all six.

**Handoff Notes:**
> _(empty — fill in if you stop here — **this phase is the most likely place someone will need to hand off mid-work, be extra detailed**)_

---

## Phase 5 — Qdrant + RAG
*(SAD reference: Chapters 09–10 — RAG Deep Dive, Qdrant)*

**Goal:** the Research Agent from Phase 4 retrieves grounded context from Qdrant instead of raw web search alone.

**Depends on:** Phase 4.

**Tasks:**
- [x] `backend/ai/rag/chunker.py` — 300–500 token chunks with overlap (Ch.09)
- [x] `backend/ai/rag/embed.py` — embedding client
- [x] `backend/ai/rag/retriever.py` — hybrid search (vector similarity + keyword overlap, Ch.09)
- [x] Create the 9 Qdrant collections from Ch.10: `scripts`, `research`, `comments`, `viewer_feedback`, `competitors`, `analytics`, `knowledge`, `prompt_history`, `lessons_learned`
- [x] Wire `backend/ai/agents/research_agent.py` to call the retriever before calling the LLM (fig 5.1's flow)
- [x] Backfill: embed and load a handful of past scripts/research from the *old* pipeline into `scripts` and `research` collections, so retrieval has something to find on day one

**Definition of Done:** a research run returns a summary that visibly cites retrieved chunks, and querying Qdrant directly shows points landing in the correct collection with correct metadata.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---

## Phase 6 — Multi-Tenancy: Channel Brain, Workspace, Channel Factory
*(SAD reference: Chapters 12b–12e — Channel Brain, User Workspace, API Providers, Tenant Isolation)*

**Goal:** the single hardcoded channel from Phase 4 becomes N database-driven channels, each isolated, created through a real onboarding flow.

**Depends on:** Phase 5 (needs Qdrant collections to namespace) and Phase 3 (needs Redis to namespace).

**Tasks:**
- [x] Retrofit Redis keys everywhere to `ch:{channel_id}:*` prefix (Ch.12b) — grep the whole codebase for raw Redis calls, there should be none left unprefixed
- [x] Retrofit every Qdrant write/query to carry mandatory `channel_id` metadata filter (Ch.12b)
- [x] `backend/tenant_platform/channels/brain.py` — the Channel Brain model (DNA, prompt library overrides, per-channel settings)
- [x] `backend/tenant_platform/factory/factory.py` — implements the exact sequence from fig 12d.1: Validate Configuration → Create Firestore Record → Create Redis Namespace → Create Qdrant Namespace → Generate Channel DNA → Channel Ready
- [x] `POST /workspaces` — creates a Workspace document on first login (Ch.12c)
- [x] `POST /channels` (replace the raw Phase 2 version) — now runs through the Channel Factory
- [x] Provider-key storage: encrypt at rest, store per channel, scoped so one channel's agents never see another channel's keys (Ch.12d table)
- [x] `backend/tenant_platform/security/permissions.py` — Permission Check middleware: Workspace ID → Channel ID → Authenticated User ID → Permission Check, in that order (Ch.12e) — wire into every router, not just channels
- [x] Write a negative test: User A's token requesting User B's channel must be rejected at the middleware layer, before touching LangGraph

**Definition of Done:** two different Firebase users can each create a channel, run the Phase 4 pipeline against their own channel independently, and neither can read, list, or trigger the other's channel — verified by an automated test, not manual inspection.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---

## Phase 7 — Async Workers (Render, Voice, Upload)
*(SAD reference: Chapter 15 — Cloud Tasks & Workers)*

**Goal:** rendering and uploading happen off the request thread, with retries.

**Depends on:** Phase 6.

**Tasks:**
- [x] Choose a task queue: Cloud Tasks (if already on GCP) or Celery + Redis broker (faster to start with, since Redis already exists from Phase 3)
- [x] `backend/app/workers/voice_worker.py` — port existing TTS logic
- [x] `backend/app/workers/render_worker.py` — port existing FFmpeg/MoviePy logic; keep the existing `-crf 28 -threads 1` OOM fix from the old pipeline
- [x] `backend/app/workers/upload_worker.py` — port existing YouTube upload logic, including the base64-encoded OAuth credential pattern already proven in the old Railway deployment
- [x] `backend/app/workers/thumbnail_worker.py`
- [x] Wire LangGraph's terminal node to enqueue a task instead of calling these directly (Ch.15)
- [x] Confirm retry-on-5xx behavior actually retries (kill a worker mid-job, confirm the task re-delivers)

**Definition of Done:** a full pipeline run from Phase 6 results in a rendered, uploaded video, and manually crashing the render worker mid-job results in an automatic retry, not a stuck job.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---

## Phase 8 — Scheduler
*(SAD reference: Chapter 16 — Cloud Scheduler)*

**Goal:** channels generate videos on their own schedule without a human triggering anything.

**Depends on:** Phase 7.

**Tasks:**
- [x] Cloud Scheduler job (or cron-triggered endpoint if deferring GCP) hitting `POST /internal/scheduler/run-due-channels`
- [x] That endpoint queries Firestore for channels whose `schedules` document says they're due, and calls Phase 6's generate endpoint for each
- [x] Reuse the existing 9 AM IST Railway scheduler's logic/timing as the reference implementation — don't redesign the scheduling rules from scratch
- [x] Confirm Scheduler-triggered requests pass through the Permission Check (Ch.12e) using a system role token, not a user JWT

**Definition of Done:** a channel with a due schedule generates a video with zero manual intervention, observed over at least one real scheduled trigger (not just a manual test call).

**Handoff Notes:**
> See `phases/phase-08-scheduler/PHASE.md` for the full handoff — short version: functionally verified end-to-end in `tests/phase8_scheduler_test.py` (30 checks), but the "real scheduled trigger" half of the Definition of Done is still open pending Phase 9's deploy target.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---

## Phase 9 — Deployment
*(SAD reference: Chapter 17 — Deployment)*

**Goal:** GitHub → GitHub Actions → Docker → hosted, on every merge to `main`.

**Depends on:** Phase 8 (or can start earlier if you want CI running from Phase 2 onward — recommended, don't wait).

**Tasks:**
- [ ] `docker/Dockerfile` for the FastAPI backend
- [ ] `.github/workflows/deploy.yml` — build, test, push, deploy on merge to `main`
- [ ] Deploy target: Cloud Run (matches the SAD) or keep Railway short-term if deferring GCP migration — document the choice here once made
- [ ] Move all secrets from local `.env` into the deploy target's secret manager
- [ ] Confirm Redis (Upstash) and Qdrant (Cloud) are reachable from the deployed environment, not just localhost

**Definition of Done:** a merge to `main` results in a live, publicly reachable `/health` endpoint returning `200`, with zero manual deploy steps.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---

## Phase 10 — Monitoring & Alerts
*(SAD reference: Chapters 18–19 — Health Agent, Alert Agent)*

**Goal:** failures are detected and escalated automatically instead of discovered by a user complaining.

**Depends on:** Phase 9.

**Tasks:**
- [ ] `backend/tenant_platform/monitoring/health_agent.py` — small LangGraph polling Redis, Firestore, Qdrant, Cloud Run, workers, Scheduler, YouTube API, LLM providers (fig 18.1)
- [ ] Trigger the Health Agent on a short interval via Scheduler (Ch.16 mechanism, reused)
- [ ] `backend/tenant_platform/monitoring/alert_agent.py` — implements the retry-then-escalate table from Ch.19, starting with the failure modes you've already hit once in the old pipeline: render failure, upload failure, YouTube quota
- [ ] Wire email + dashboard notification on escalation
- [ ] Incident Report written to Firestore on escalation, with a "pause this channel's schedule" action for serious failures

**Definition of Done:** manually killing Redis (or simulating it) results in an alert reaching your inbox within the polling interval, not silence.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---

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
> _(empty — fill in if you stop here)_

---

## Phase 12 — Learning Agent
*(SAD reference: Chapter 20 — Learning Agent)*

**Goal:** channels get measurably better over time using their own performance history.

**Depends on:** Phase 11, and — practically — at least a few weeks of real analytics data. Don't start this phase early; it has nothing to learn from yet.

**Tasks:**
- [ ] `backend/ai/agents/learning_agent.py` — pattern detection over each channel's own `analytics` collection (never cross-channel, per Ch.12e isolation)
- [ ] Write confirmed patterns into Qdrant's `lessons_learned` collection with `channel_id` metadata
- [ ] Confirm the Research/Planner agents actually retrieve from `lessons_learned` on subsequent runs (closing the loop from fig 20.1)
- [ ] Schedule this agent to run periodically via the Phase 8 scheduler mechanism

**Definition of Done:** a lesson written by the Learning Agent for Channel A is retrievable by Channel A's next Research run, and is *not* retrievable by Channel B's run.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---

## 3. Cross-Phase Reference Table

Quick lookup — "which phase owns this thing":

| Component | Owning Phase | SAD Chapter |
|---|---|---|
| Firebase Auth / Firestore | 1 | 12 |
| FastAPI shell | 2 | 03 |
| Redis / rate limiter | 3 | 11 |
| LangGraph engine + core agents | 4 | 04–08 |
| RAG / Qdrant | 5 | 09–10 |
| Channel Brain / Factory / Isolation | 6 | 12b–12e |
| Async workers | 7 | 15 |
| Scheduler | 8 | 16 |
| CI/CD & hosting | 9 | 17 |
| Health & Alert agents | 10 | 18–19 |
| Frontend dashboard | 11 | 00, 0.5, 03 |
| Learning Agent | 12 | 20 |

Future roadmap items (multi-platform publishing, A/B testing, Sponsor Agent, etc. — SAD Chapter 22) are intentionally **not** phases here. Don't start them until Phase 12 is stable — each one assumes the full loop above already works.

---

## 4. Definitions, For Anyone New To The Project

- **SAD** — the Software Architecture Document (`docs/architecture/AI-CarryON-Architecture.html`), the reference for *why* things are designed this way.
- **This file** — the build order and handoff log, for *what to actually do, and where we left off*.
- If the two ever disagree, the SAD wins on design intent; this file wins on current build status.
