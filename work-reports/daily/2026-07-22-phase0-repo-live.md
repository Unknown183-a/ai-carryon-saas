# Work Report — 2026-07-22

**Phase worked on:** Phase 0 — Repo & Skeleton
**Author:** Amit
**Time spent:** ~1 hr

## What I built / did

- Set up the full project scaffold: folder skeleton, docs, per-phase briefs, work-reports structure.
- Reorganized `backend/` from technology-based folders (api, langgraph, redis, ...) to responsibility-based (`app/`, `ai/`, `platform/`, `integrations/`, `configs/`), based on a review pass.
- Reconciled a few ambiguous additions: clarified `ai/models/` (model registry/routing) vs `app/models/` (API/Firestore schemas) vs `integrations/` (raw provider clients); split `channel_factory/` into `channels/` + `factory/`; added `platform/security/` and `docs/{api,decisions,deployment,diagrams}/`.
- Created the GitHub repo (`Unknown183-a/ai-carryon-saas`) and pushed the initial history.

## What's now working (proof, not vibes)

- `git push -u origin main` succeeded — repo is live at github.com/Unknown183-a/ai-carryon-saas with 5 commits, all folders present and README rendering correctly on the repo homepage.

## What broke / what I couldn't finish

- First push was rejected: `refusing to allow a Personal Access Token to create or update workflow .github/workflows/README.md without workflow scope`. Tried updating the token's scope in GitHub settings, but the push still failed on retry — token change likely didn't save.
- Worked around it by removing `.github/workflows/README.md` from the commit (`git rm --cached`) and pushing without it. `.github/workflows/` is now empty and won't reappear in the repo until Phase 9 adds a real workflow file — expected, not a bug.

## Decisions made (and why)

- Kept the token-scope problem unresolved rather than blocking on it — Phase 9 is the actual point that folder matters, so deferring is fine.
- Adopted the responsibility-based `backend/` layout over the original technology-based one; it scales better as the codebase grows.

## Next concrete step

Start Phase 1 — enable Email/Password sign-in in the Firebase console, per `phases/phase-01-firebase-auth-firestore/PHASE.md`.

## Checkboxes ticked this session

- [x] Phase 0: Run the skeleton command below
- [x] Phase 0: Commit with message `chore: initial folder skeleton`
- [x] Phase 0: Add `.env` to `.gitignore`, commit `.env.example` instead
- [x] Phase 0: Add a root `README.md` that just links to this file and the SAD
