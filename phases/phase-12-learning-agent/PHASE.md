<!-- Self-contained phase brief. Companion docs: ../../docs/BUILD_GUIDE.md (full build order) and ../../docs/AI-CarryON-Architecture-Document.html (the why). -->

## Phase 12 — Learning Agent
*(SAD reference: Chapter 20 — Learning Agent)*

**Goal:** channels get measurably better over time using their own performance history.

**Depends on:** Phase 11, and — practically — at least a few weeks of real analytics data. Don't start this phase early; it has nothing to learn from yet.

**Tasks:**
- [ ] `backend/agents/learning_agent.py` — pattern detection over each channel's own `analytics` collection (never cross-channel, per Ch.12e isolation)
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

- **SAD** — the Software Architecture Document (`AI-CarryON-Architecture-Document.html`), the reference for *why* things are designed this way.
- **This file** — the build order and handoff log, for *what to actually do, and where we left off*.
- If the two ever disagree, the SAD wins on design intent; this file wins on current build status.
