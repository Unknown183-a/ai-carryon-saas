<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 8 — Scheduler
*(SAD reference: Chapter 16 — Cloud Scheduler)*

**Goal:** channels generate videos on their own schedule without a human triggering anything.

**Depends on:** Phase 7.

**Tasks:**
- [ ] Cloud Scheduler job (or cron-triggered endpoint if deferring GCP) hitting `POST /internal/scheduler/run-due-channels`
- [ ] That endpoint queries Firestore for channels whose `schedules` document says they're due, and calls Phase 6's generate endpoint for each
- [ ] Reuse the existing 9 AM IST Railway scheduler's logic/timing as the reference implementation — don't redesign the scheduling rules from scratch
- [ ] Confirm Scheduler-triggered requests pass through the Permission Check (Ch.12e) using a system role token, not a user JWT

**Definition of Done:** a channel with a due schedule generates a video with zero manual intervention, observed over at least one real scheduled trigger (not just a manual test call).

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---
