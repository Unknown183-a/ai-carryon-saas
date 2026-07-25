"""
Phase 9 — Deployment reachability smoke test.

What this proves (per phases/phase-09-deployment/PHASE.md's third pending
task): Redis (Upstash) and Qdrant (Cloud) are reachable from somewhere
other than your own laptop — i.e. the same public HTTPS endpoints Cloud
Run will call at runtime, not just "works on localhost". This is a
real-keys test, same convention as Phase 5/6's real-keys smoke tests —
it needs actual UPSTASH_REDIS_REST_URL/TOKEN and QDRANT_URL/API_KEY set,
not fakes, and is meant to be run manually (not in CI, same reason
tests/phase1_firebase_test.py is CI-skipped: it talks to real external
accounts).

Run locally, or better, from inside the deployed Cloud Run container
itself for the strongest version of this proof:

    # Locally (proves the endpoints are reachable from the public
    # internet at all — a reasonable first check):
    python tests/phase9_deployed_reachability_test.py

    # From the deployed container (proves it specifically from Cloud
    # Run's network — the stronger version of PHASE.md's actual claim):
    gcloud run services proxy ai-carryon-gateway --region asia-south1 &
    # then, in a separate shell, exec into a one-off revision or use
    # `gcloud run jobs execute` if this is wired as a Job; simplest today
    # is curling the deployed /health (below) plus running this script
    # locally with the same real creds — both point at the same public
    # endpoints, so a pass on both is strong evidence the deployed
    # container's egress isn't the difference.

Also curls the deployed /health if DEPLOYED_BASE_URL is set (the
ai-carryon-gateway service's URL), so one run of this script can confirm
several things at once: deploy target live, secrets present (implied by
Redis/Qdrant creds being real and working), and reachability.

Doubles as the worker-side reachability check docs/deployment/README.md
notes is missing: that README says there's "no equivalent single
endpoint to check business-logic health" for ai-carryon-worker, since
its $PORT-listening health check (worker_entrypoint.py) only proves the
container is alive, not that it can actually reach Redis/Qdrant. This
script's Redis/Qdrant checks aren't tied to any HTTP endpoint at all —
running it with the same real credentials the worker uses is a direct
proxy for "can the worker's process actually reach these", without
needing to queue a real task and watch logs.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import httpx

from app.core.redis_client import get_redis
from app.core.qdrant_client import get_qdrant


def check_redis() -> bool:
    required = ["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"  SKIP  Redis — missing env var(s): {', '.join(missing)}")
        return False

    try:
        redis = get_redis()
        probe_key = "phase9:reachability_probe"
        redis.set(probe_key, "ok", ex=30)
        value = redis.get(probe_key)
        redis.delete(probe_key)
        if value == "ok":
            print("  PASS  Redis (Upstash) — set/get round-trip succeeded")
            return True
        print(f"  FAIL  Redis (Upstash) — unexpected round-trip value: {value!r}")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL  Redis (Upstash) — {exc}")
        return False


def check_qdrant() -> bool:
    required = ["QDRANT_URL"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"  SKIP  Qdrant — missing env var(s): {', '.join(missing)}")
        return False

    try:
        qdrant = get_qdrant()
        # Any real collection created by Phase 5's ensure_collections() at
        # startup works here — "research" is one of the nine Ch.10 collections.
        exists = qdrant.collection_exists("research")
        print(f"  PASS  Qdrant Cloud — reachable, 'research' collection exists: {exists}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL  Qdrant Cloud — {exc}")
        return False


def check_deployed_health() -> bool:
    base_url = os.environ.get("DEPLOYED_BASE_URL")
    if not base_url:
        print("  SKIP  Deployed /health — DEPLOYED_BASE_URL not set")
        return False

    try:
        response = httpx.get(f"{base_url.rstrip('/')}/health", timeout=10.0)
        response.raise_for_status()
        body = response.json()
        if body.get("status") == "ok":
            print(f"  PASS  Deployed /health at {base_url} — {body}")
            return True
        print(f"  FAIL  Deployed /health at {base_url} — unexpected body: {body}")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL  Deployed /health at {base_url} — {exc}")
        return False


def main() -> int:
    print("Phase 9 reachability check\n")
    results = {
        "redis": check_redis(),
        "qdrant": check_qdrant(),
        "deployed_health": check_deployed_health(),
    }

    ran = [k for k, v in results.items() if v]
    print(f"\n{len(ran)}/3 checks passed: {ran or 'none'}")

    # Deployed health is optional (only runs if DEPLOYED_BASE_URL is set);
    # Redis and Qdrant are the actual Phase 9 reachability claim, so those
    # two are what gate exit status.
    if results["redis"] and results["qdrant"]:
        return 0
    print("\nRedis and/or Qdrant checks did not pass — see SKIP/FAIL lines above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
