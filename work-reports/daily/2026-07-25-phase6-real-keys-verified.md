# Work Report — 2026-07-25 (later)

**Phase worked on:** Phase 6 follow-up — real-keys verification, plus two Phase 4 prompt fixes
**Author:** Claude
**Time spent:** ~1 hr

## What happened

Ran `tests/phase6_real_keys_smoke_test.py` — two real Firebase Auth users, real ID tokens (custom-token → `signInWithCustomToken` exchange), driving the real FastAPI app with no auth dependency override, so `get_current_user`'s actual `firebase_admin.auth.verify_id_token()` ran for real.

## Phase 6's own logic: zero bugs found

Every isolation check passed on the first run:
- Independent workspaces and channels for two different users
- `GET /channels` never cross-leaked either user's channel to the other
- User B's token against User A's channel_id correctly got `403`
- An unknown `channel_id` correctly got `404`, not `403`

This is the actual Definition of Done for this phase, and it held up completely.

## What the real run did surface: two bugs, but not in Phase 6

**Bug 1 — Grammar Check too strict.** User B's own pipeline run in the two-user test returned `status: failed`, `"script exceeded 3 retries"`. The flagged "issues" were word-choice consistency ("released" vs "introduced to the market") and a passive-voice preference — not grammar errors. Fixed `grammar_check_prompt()` in `backend/ai/prompts/prompt_library.py` with explicit "do NOT fail for" guidance. Confirmed with a real single-user re-run: Grammar Check passed clean (`pass: true, issues: []`).

**Bug 2 — Copyright Check too strict.** That same confirmation run then hit the retry cap on a *different* check: Copyright Check flagged the script and its own description as containing "copied or similar passages" between each other — e.g. both mentioning "a surge in new AI model releases." That's expected overlap (a script and its description are supposed to cover the same video), not copying. Same root cause as Bug 1: the prompt didn't clarify the check should compare against external sources, not the two given texts against each other. Fixed `copyright_check_prompt()` the same way.

**Final confirmation run, after both fixes:** full pass, first try, zero retries — all four review gates (grammar, fact, copyright, LLM judge) green.

## Decisions made (and why)

- **Used cheap single-user diagnostic runs to isolate each bug** rather than re-running the full two-user test (~20 real LLM calls) after every fix — same real verification rigor, lower cost per iteration.
- **Kept testing after each fix instead of declaring victory** — the Grammar Check fix genuinely worked and could have been mistaken for "done," but the very same run immediately surfaced the Copyright Check bug. Assuming success after one fix would have shipped a still-broken review gate.
- **Documented both fixes in Phase 4's `PHASE.md`**, not Phase 6's, since that's where `prompt_library.py` actually lives — Phase 6's handoff notes get an UPDATE note pointing there instead of duplicating the detail.

## Next concrete step

Phase 7 — Async Workers, per `STATUS.md`. Phases 1-6 are now fully real-verified with no open blocking items; the only remaining low-priority gap across all of them is `backend/ai/rag/backfill.py` never having been run against a real old-pipeline export (none exists yet to test against).
