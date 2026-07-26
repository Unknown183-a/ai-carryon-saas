# Work Report — 2026-07-26

**Phase:** 9 — Deployment

**What I did:**
- Decided on Cloud Run as the Phase 9 deploy target (matches the SAD, Ch.17; keeps the stack on GCP alongside Firebase)
- Finalized `.github/workflows/deploy.yml` — uncommented and completed the `deploy` job: `google-github-actions/auth` + `deploy-cloudrun`, every `.env.example` secret wired in via `--set-secrets`, a post-deploy `/health` check
- Added `docker-compose.yml` for local API + worker testing (Redis/Qdrant stay cloud-hosted even locally, matching prod)
- Wrote `docs/deployment/README.md`: GCP service account setup, the `gcloud secrets create` migration commands, key rotation steps, reachability confirmation, and rollback via `update-traffic`
- Updated `phases/phase-09-deployment/PHASE.md` checkboxes and handoff notes
- Updated `STATUS.md`

**What's left:**
- Someone with GCP account access needs to run the one-time service-account creation + secret migration commands from the runbook, then add `GCP_SA_KEY` / `GCP_PROJECT_ID` as GitHub repo secrets
- Once those exist, the next merge to `main` should complete Phase 9's Definition of Done with no further code changes
