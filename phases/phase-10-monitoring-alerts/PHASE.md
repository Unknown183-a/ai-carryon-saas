<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 10 — Monitoring & Alerts
*(SAD reference: Chapters 18–19 — Health Agent, Alert Agent)*

**Goal:** failures are detected and escalated automatically instead of discovered by a user complaining.

**Depends on:** Phase 9.

**Tasks:**
- [ ] `backend/platform/monitoring/health_agent.py` — small LangGraph polling Redis, Firestore, Qdrant, Cloud Run, workers, Scheduler, YouTube API, LLM providers (fig 18.1)
- [ ] Trigger the Health Agent on a short interval via Scheduler (Ch.16 mechanism, reused)
- [ ] `backend/platform/monitoring/alert_agent.py` — implements the retry-then-escalate table from Ch.19, starting with the failure modes you've already hit once in the old pipeline: render failure, upload failure, YouTube quota
- [ ] Wire email + dashboard notification on escalation
- [ ] Incident Report written to Firestore on escalation, with a "pause this channel's schedule" action for serious failures

**Definition of Done:** manually killing Redis (or simulating it) results in an alert reaching your inbox within the polling interval, not silence.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---
