# Work Report — 2026-07-26

**Phase worked on:** Phase 10 — Monitoring & Alerts (full build)
**Author:** Claude
**Time spent:** ~2 hours

## What I built / did

- `backend/tenant_platform/monitoring/health_agent.py` — a small LangGraph, fan-out to 7 check
  nodes (Redis, Firestore, Qdrant, Celery workers, Scheduler staleness, YouTube API, LLM provider
  key presence), AND-join into an `aggregate` node — same fan-out/join shape as
  `ai/langgraph/graph.py`'s Parallel Generation agents.
- `backend/tenant_platform/monitoring/alert_agent.py` — retry-then-escalate table (`render_failure`,
  `upload_failure`, `youtube_quota`, plus a `health:*` catch-all for health_agent's own checks),
  Redis-backed retry counters, Firestore incident reports + dashboard notifications + Resend email
  on escalation, and a schedule-pause action for serious failures.
- `backend/integrations/resend/client.py` — thin httpx wrapper, same one-function-raise-on-failure
  pattern as the other integrations. Resend chosen over Gmail SMTP/SendGrid in this session's
  scoping conversation.
- `backend/integrations/youtube/client.py` — added `check_connection()`, a 1-quota-unit
  `channels.list(mine=True)` call, structured result instead of raising (a health check must not
  crash the poll).
- `backend/app/database/firestore_collections.py` — added `INCIDENTS`/`NOTIFICATIONS` collections,
  `create_incident_report`, `list_incidents`, `create_notification`, `list_notifications`,
  `mark_notification_read`, `set_schedule_enabled`.
- `backend/app/api/routers/internal_health.py` — `POST /internal/health-check/run`, same
  `require_system_token` gate as Phase 8's scheduler endpoint, meant for its own separate Cloud
  Scheduler job on a short interval.
- `backend/app/api/routers/notifications.py` — `GET /workspaces/{id}/notifications`,
  `POST /notifications/{id}/read`.
- `main.py` — wired both new routers in, updated the module docstring.
- `.env.example` — `RESEND_API_KEY`, `ALERT_EMAIL_FROM`, `ALERT_EMAIL_TO`.
- `tests/phase10_monitoring_test.py` — fake-first test script (same convention as Phase 3/6/9):
  a real `FakeUpstash` (reused shape from Phase 3's test) wired into the real `RedisClient`, a
  real small `FakeFirestore`, faked Qdrant/Celery/YouTube/Resend — running the **actual**
  `health_agent.py`/`alert_agent.py` code, not mocks of it.

## What's now working (proof, not vibes)

- `tests/phase10_monitoring_test.py`: 24/24 checks pass, including the Definition of Done itself
  (simulated Redis outage → escalation → captured "email", addressed correctly, subject correct).
- The LangGraph graph was confirmed to actually *compile and run* (not just import cleanly) via a
  standalone `asyncio.run(health_agent.run_health_check(...))` against faked services before the
  test script existed.
- The whole FastAPI app was confirmed to boot with both new routers registered, using a real
  `fastapi.testclient.TestClient`: `POST /internal/health-check/run` returns `401` with no token,
  `403` with a wrong one, `200` with the right one — and that `200` response is the real output of
  the real `health_agent.py` → `alert_agent.py` code path, not a stub.

## What broke / what I couldn't finish

- **A real bug, caught by the test itself and fixed in this session:** the retry counter for every
  failure mode — including `health:redis` — originally lived in Redis. If Redis is genuinely down,
  `record_failure` would crash trying to track that Redis is down, instead of alerting on it. Fixed:
  Redis calls inside `record_failure`/`record_success` are now wrapped; if they fail, retry-counting
  is skipped entirely and escalation happens immediately, deduped with an in-process set instead of
  a Redis-backed one. See `alert_agent.py`'s `_redis_down_escalated` comment for the accepted
  trade-off (a possible duplicate alert across a process restart mid-outage — much better than
  silence).
- **No real credentials were available in this session** — same shape as Phase 9's own gap. Nothing
  here has been run against real Redis/Qdrant/Firestore/YouTube/Resend, and no real Cloud Scheduler
  job exists yet (needs Phase 9's live Cloud Run URL to point at first).

## Decisions made (and why)

- Resend over Gmail SMTP/SendGrid — user's choice in this session's scoping question; modern REST
  API, no SMTP session management, generous free tier for low-volume alert traffic.
- LLM provider health check is presence-only (env var set or not), not a live API call — avoids a
  real per-poll dollar cost against 3 providers for a check mostly aimed at "someone forgot to
  rotate a key in Secret Manager." A present-but-invalid key surfaces through a real generation
  run's own failure path instead.
- Health Agent gets its own separate Cloud Scheduler job/timer rather than piggybacking on Phase 8's
  "due channels" poll — that one only fires when a channel is actually due (could be days apart on
  a weekly schedule), which doesn't satisfy "detect a Redis outage within the polling interval"
  regardless of any channel's own schedule.
- Platform-level (non-channel) failures use the literal `channel_id` value `"platform"` rather than
  `None`, to stay inside every other Firestore query pattern in this file that assumes `channel_id`
  is always a meaningful, queryable string.

## Next concrete step

Do Phase 9's operational steps first (real GCP project, `deployment/gcp/README.md`'s 5 steps) —
Phase 10's own remaining step (create a second Cloud Scheduler job pointed at
`/internal/health-check/run`) needs that live URL to exist. After that, this phase is fully closed,
no more code needed.

## Checkboxes ticked this session

- [x] `backend/tenant_platform/monitoring/health_agent.py`
- [x] Trigger the Health Agent on a short interval via Scheduler (Ch.16 mechanism, reused)
- [x] `backend/tenant_platform/monitoring/alert_agent.py`
- [x] Wire email + dashboard notification on escalation
- [x] Incident Report written to Firestore on escalation, with a "pause this channel's schedule" action
