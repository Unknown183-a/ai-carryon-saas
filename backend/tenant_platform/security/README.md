Owned by: **Phase 6 — multi-tenancy-channel-factory**.

Tenant isolation & permission checking (SAD Ch.12e): `permissions.py` — the Workspace ID →
Channel ID → Authenticated User ID → Permission Check chain, wired into every router. Also
where provider-key encryption-at-rest lives (Ch.12d table) — one channel's agents must never
see another channel's keys.

See `../../../phases/phase-06-multi-tenancy-channel-factory/PHASE.md`.
