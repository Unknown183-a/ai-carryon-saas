# Work Report — 2026-07-25

**Phase worked on:** Phase 6 — Multi-Tenancy: Channel Brain, Workspace, Channel Factory
**Author:** Claude
**Time spent:** ~3 hrs

## What I built / did

**Redis/Qdrant retrofit (Ch.12b):**
- `redis_client.py` — added `channel_key(channel_id, suffix)` helper
- `trend_agent.py`, `research_agent.py` — cache keys rebuilt through it
- `embed.py` — now requires `channel_id` as a parameter; `retriever.py`'s two call sites updated to pass it
- `rate_limit.py` — added a per-channel counter alongside the existing per-user one, for any `/channels/{channel_id}/...` route (resolves that file's own pre-existing TODO)
- Qdrant: already complete from Phase 5 (`channel_id` was already a required, enforced parameter) — confirmed, not rebuilt

**Bug caught and fixed before writing any Phase 6 code:** `backend/platform/` (the path the SAD/brief use) collides with Python's stdlib `platform` module. Verified empirically that this breaks any library doing `import platform` once `backend/` is on `sys.path` (this codebase's established convention). Renamed to `backend/tenant_platform/`, documented why in a new README there, and updated the other docs (`backend/README.md`, top-level `README.md`, `BUILD_GUIDE.md`, Phase 10's still-open brief) that reference the path.

**New modules:**
- `app/models/workspace.py`, `app/models/channel.py` — Pydantic schemas (`Workspace`, `ChannelCreateRequest`, `ProviderKeys`, `ChannelBrand`)
- `app/database/firestore_collections.py` — data-access layer (workspaces, channels, provider keys)
- `tenant_platform/security/provider_keys.py` — Fernet encryption at rest for provider keys (Ch.12d)
- `tenant_platform/security/permissions.py` — `require_channel_access`, the Ch.12e isolation chain as a FastAPI dependency
- `tenant_platform/channels/brain.py` — `ChannelBrain` / `load_channel_brain()` / `to_pipeline_config()`
- `tenant_platform/factory/factory.py` — `create_channel()`, the full fig 12d.1 sequence
- `app/api/routers/workspaces.py` — `POST /workspaces`
- `app/api/routers/channels.py` — rewritten: `GET/POST /channels` now workspace-aware and factory-backed; `POST /channels/{id}/generate` now gated by `require_channel_access` and loads a real `ChannelBrain` instead of Phase 4's hardcoded one
- `app/api/main.py` — wired the new `workspaces` router in

**Tests:**
- `tests/phase6_multi_tenancy_test.py` — new, 23 checks, everything faked in-process (added a `FakeFirestore` double alongside the existing FakeUpstash/FakeQdrant/fake-LLM machinery from Phase 4/5)
- `tests/phase4_langgraph_test.py` — Test 1 adjusted: it drove the pipeline through the now-superseded hardcoded HTTP route; changed to call the LangGraph engine directly (same pattern Test 2 always used), since that's what it actually needs to keep proving

## What's now working (proof, not vibes)

`tests/phase6_multi_tenancy_test.py`, condensed:
```
=== Test 1: User A creates a workspace, a channel, and runs the pipeline ===
✅ POST /workspaces (User A) returns 200
✅ workspace has User A as a member
✅ POST /workspaces is idempotent (same workspace_id on second call)
✅ POST /channels (User A) returns 200
✅ channel status is 'ready' after the Factory chain completes
✅ channel is attached to User A's workspace
✅ factory wrote a ch:{channel_id}:* Redis namespace marker
✅ provider key was stored encrypted, not as plaintext
✅ POST /channels/{id}/generate (User A, own channel) returns 200
✅ User A's run produced a script / SEO / review_verdict == pass
✅ research cache key is ch:{channel_id}:-namespaced

=== Test 2: User B independently creates their own workspace, channel, and run ===
✅ User B's workspace is different from User A's
✅ User B's channel is different from User A's
✅ POST /channels/{id}/generate (User B, own channel) returns 200

=== Test 3: Ch.12e isolation — list, and trigger, both ways ===
✅ User A's channel list never includes User B's channel
✅ User B's channel list never includes User A's channel
✅ User B requesting User A's channel gets 403
✅ graph.ainvoke was never called for the rejected request
✅ User A requesting User B's channel gets 403 (symmetric)
✅ graph.ainvoke still never called
✅ requesting a channel that doesn't exist at all gets 404, not 403

23 passed, 0 failed
```

The `graph.ainvoke` checks aren't just status-code checks — a tripwire graph object raises `AssertionError` if `ainvoke` is ever called, so those two checks prove the rejection happens before the pipeline layer, not just that the HTTP response looks right.

Re-ran Phase 4 and Phase 5's suites afterward: Phase 5 passes unchanged (13/13). Phase 4 needed the Test 1 adjustment described above; after that, 100% passes, and it now proves something arguably more honest — that the LangGraph engine itself still works — without conflating that with routing behavior that legitimately changed this phase.

## What broke / what I couldn't finish

One real bug, caught before it caused damage: the `platform`/stdlib collision, described above and in PHASE.md's handoff notes in detail (with the exact `AttributeError` it would have caused). Nothing else broke — the FakeFirestore double needed one iteration (the dependency-override function needed `request: Request` type-annotated for FastAPI to inject it rather than treat it as a query parameter), and the fix was immediate once diagnosed.

Not done, not attempted: no real Firebase project, Firestore, Redis, or Qdrant was exercised — every check in every test suite so far (Phases 3-6) has been against faked services. This is now a fairly large accumulated gap and is called out plainly in STATUS.md and this phase's PHASE.md handoff notes.

## Decisions made (and why)

- **`backend/platform/` → `backend/tenant_platform/`** — real stdlib collision, not a naming preference; see above.
- **Permission Check as a FastAPI dependency, not raw ASGI middleware** — Ch.12e's prose says "middleware," but a dependency runs at the same point in the request lifecycle for any route that declares it, and can cleanly `Depends()` on existing auth/Firestore dependencies instead of re-implementing them.
- **`POST /workspaces` is a plain endpoint the frontend calls after login, not a Cloud Function trigger on email verification** — Ch.12c describes the latter, but no Cloud Functions deployment exists in this project yet. Idempotent, so calling it on every login is always safe.
- **Provider keys encrypted with one platform-wide Fernet key, not per-channel keys** — Ch.12d's isolation guarantee is about which channel's *row* decrypts to which values (true here), not about key-management topology. Per-channel KMS is a bigger system this project doesn't need yet.
- **`ChannelBrain` holds DNA + prompt overrides, not all eight of Ch.12b's listed components** — Redis/Qdrant namespaces are conventions enforced elsewhere, not data; Analytics/Learning/Viewer Feedback/Competitor Memory are Qdrant collections that are already per-channel by construction once later phases write to them, with no change needed here.

## Next concrete step

Begin Phase 7 (`phases/phase-07-async-workers/PHASE.md`). Strongly worth a slight detour first, given how much has now accumulated: spend 30-60 minutes doing one real end-to-end pass — actual Firebase project, actual `.env`, `POST /workspaces` → `POST /channels` → `POST /channels/{id}/generate` against real Redis/Qdrant/Gemini — before adding a fourth phase's worth of faked-only surface area on top.

## Checkboxes ticked this session

- [x] Retrofit Redis keys everywhere to `ch:{channel_id}:*` prefix (Ch.12b)
- [x] Retrofit every Qdrant write/query to carry mandatory `channel_id` metadata filter (Ch.12b) — confirmed already done in Phase 5
- [x] `backend/tenant_platform/channels/brain.py`
- [x] `backend/tenant_platform/factory/factory.py`
- [x] `POST /workspaces`
- [x] `POST /channels` (replace the raw Phase 2 version) — now runs through the Channel Factory
- [x] Provider-key storage: encrypt at rest, store per channel
- [x] `backend/tenant_platform/security/permissions.py`
- [x] Negative test: User A's token requesting User B's channel rejected before touching LangGraph
