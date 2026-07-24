# Work Report — 2026-07-24

**Phase worked on:** Phase 9 — Deployment (CI/CD half only — built as an independent side-track while Phase 4 stays in progress)
**Author:** Claude
**Time spent:** ~1 hr

## What I built / did

- `docker/Dockerfile` — builds `backend/` using `backend/requirements.txt`, runs `uvicorn app.api.main:app`, reads `$PORT` for Cloud Run compatibility, defaults to 8080 for local `docker run`.
- `.github/workflows/deploy.yml` — three jobs:
  - `test`: installs `backend/requirements.txt`, runs `tests/phase3_redis_ratelimit_test.py` directly.
  - `build`: on `main` only, builds the Dockerfile and pushes to `ghcr.io/<repo>` using the built-in `GITHUB_TOKEN` (no extra secrets needed).
  - `deploy`: documented no-op stub with commented Cloud Run and Railway steps, since the deploy target isn't chosen yet.
- Confirmed which phase was actually independent of Phase 4 by reading `BUILD_GUIDE.md`'s dependency chain end to end — Phase 9 is the only one the guide explicitly says can start early.

## What's now working (proof, not vibes)

GitHub Actions run for commit `b11c227` on `main`: `test` ✅ (16s), `build` ✅ (pushed image), `deploy` ✅ (stub, ran the no-op echo). Image confirmed visible under the repo's Packages tab as `ghcr.io/unknown183-a/ai-carryon-saas` with `latest` and commit-SHA tags.

## What broke / what I couldn't finish

- First run failed: `tests/phase1_firebase_test.py` and `phase3_redis_ratelimit_test.py` aren't pytest-shaped (they're standalone scripts, per their own docstrings — "Run with: python phaseN_test.py"). Running them under `pytest` made it try to *import* `phase1_firebase_test.py`, which reads `os.environ["FIREBASE_PROJECT_ID"]` at module level — `KeyError` in CI since no `.env` exists there. Fixed by dropping pytest entirely: `test` job now runs Phase 3's script directly (it self-mocks Upstash, so it's CI-safe) and explicitly skips Phase 1's script with an echoed note, since that one needs a real Firebase project + service account and creates/deletes a live user — not something CI should ever do unattended.
- Second run failed: `build` job errored with `invalid tag ... repository name must be lowercase` — `github.repository` evaluates to `Unknown183-a/ai-carryon-saas`, and Docker/ghcr.io reject uppercase in image names. Fixed by adding a step that lowercases it into `$GITHUB_ENV` before the tag is built.
- Deploy target (Cloud Run vs Railway) still undecided — left as a stub on purpose rather than guessing.

## Decisions made (and why)

- Pushed images to GHCR instead of GCP Artifact Registry for now — it needs zero extra account setup (`GITHUB_TOKEN` already has package-write via repo settings), so CI is fully live today; whichever deploy target gets picked later can pull from GHCR just as easily as from GCP's own registry.
- Didn't touch `tests/phase1_firebase_test.py` itself — it's correctly written as a manual/local integration check per Phase 1's own `PHASE.md`; the fix belongs in the CI workflow (don't run it there), not in the test file.

## Next concrete step

Phase 4 continues as the primary active phase (see `STATUS.md`). Phase 9 has one task left whenever it's picked back up: choose Cloud Run or Railway as the deploy target, add the matching secret(s), and uncomment that block in `.github/workflows/deploy.yml`.

## Checkboxes ticked this session

- [x] Phase 9: `docker/Dockerfile` for the FastAPI backend
- [x] Phase 9: `.github/workflows/deploy.yml` — build, test, push, deploy on merge to `main`
