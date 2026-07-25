"""
Phase 6 — REAL KEYS smoke test.

Companion to tests/phase4_real_keys_smoke_test.py and
tests/phase5_real_keys_smoke_test.py. Unlike
tests/phase6_multi_tenancy_test.py (everything faked, including
Firestore), this creates two REAL Firebase Auth users, mints REAL ID
tokens for each, and drives the REAL FastAPI app — with NO auth
dependency override — so `get_current_user`'s real
`firebase_admin.auth.verify_id_token()` actually runs, the way a real
client's requests would hit it.

Proves this phase's actual Definition of Done: "two different Firebase
users can each create a channel, run the Phase 4 pipeline against their
own channel independently, and neither can read, list, or trigger the
other's channel." The faked test proves the wiring; this proves it
against a real Firebase project, real Firestore, and (since a channel
run means a real pipeline run) real Gemini/Groq/Serper/Redis/Qdrant too.

Cost note: this makes TWO full real pipeline runs (one per user) — each
one is Phase 4's ~10 real LLM calls plus Phase 5's embedding/Qdrant
calls, so this script is roughly double the cost of running
phase5_real_keys_smoke_test.py once. Cheap on free tiers, but not a
script to loop.

Run with:
    python phase6_real_keys_smoke_test.py

Requires everything phase5_real_keys_smoke_test.py needs, plus:
    FIREBASE_PROJECT_ID
    FIREBASE_SERVICE_ACCOUNT_JSON
    FIREBASE_WEB_API_KEY   (Firebase console -> Project settings -> General
                             -> Web API Key -- NOT the service account)

Creates and deletes two real Firebase Auth users and their Firestore
documents (workspaces/channels/channel_provider_keys) as part of this
run. If the script is interrupted before cleanup, the users will be
named phase6-test-a-<uuid>@example.com / phase6-test-b-<uuid>@example.com
and are safe to delete by hand from the Firebase console.
"""

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

REQUIRED_ENV_VARS = [
    "FIREBASE_PROJECT_ID",
    "FIREBASE_SERVICE_ACCOUNT_JSON",
    "FIREBASE_WEB_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "SERPER_API_KEY",
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "CHANNEL_SECRETS_ENCRYPTION_KEY",
]

missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
if missing:
    print(f"❌ Missing required .env values: {missing}")
    print("   Add them to .env at the repo root, then re-run this script.")
    sys.exit(1)

import requests
from fastapi.testclient import TestClient
from firebase_admin import auth

from app.api.middleware.auth import init_firebase  # noqa: E402
from app.api.main import app  # noqa: E402
from app.database.firestore_collections import WORKSPACES, CHANNELS, PROVIDER_KEYS  # noqa: E402

init_firebase()
from firebase_admin import firestore as admin_firestore  # noqa: E402

db = admin_firestore.client()
client = TestClient(app)

FIREBASE_WEB_API_KEY = os.environ["FIREBASE_WEB_API_KEY"]

created_uids: list[str] = []
created_doc_refs: list = []  # (collection, doc_id) tuples for cleanup


def create_real_test_user(label: str) -> tuple[str, str]:
    """Creates a real Firebase Auth user and returns (uid, real_id_token)."""
    email = f"phase6-test-{label}-{uuid.uuid4().hex[:8]}@example.com"
    user = auth.create_user(email=email, password="TestPassword123!")
    created_uids.append(user.uid)

    custom_token = auth.create_custom_token(user.uid).decode("utf-8")
    exchange_url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"
        f"?key={FIREBASE_WEB_API_KEY}"
    )
    resp = requests.post(exchange_url, json={"token": custom_token, "returnSecureToken": True})
    resp.raise_for_status()
    id_token = resp.json()["idToken"]
    return user.uid, id_token


def auth_headers(id_token: str) -> dict:
    return {"Authorization": f"Bearer {id_token}"}


def cleanup():
    print("\n=== Cleanup: deleting test users and Firestore docs ===")
    for collection, doc_id in created_doc_refs:
        try:
            db.collection(collection).document(doc_id).delete()
        except Exception as exc:
            print(f"⚠️  Failed to delete {collection}/{doc_id}: {exc}")
    for uid in created_uids:
        try:
            auth.delete_user(uid)
        except Exception as exc:
            print(f"⚠️  Failed to delete user {uid}: {exc}")
    print("✅ Cleanup done.")


async def run_channel_generation_via_http(id_token: str, channel_id: str):
    """Calls POST /channels/{id}/generate through the real HTTP layer.
    TestClient is sync, but the route itself is async and makes real
    outbound network calls (LLM/Qdrant/Redis) — those go out over the
    real network same as any other outbound call this process makes.
    """
    return client.post(f"/channels/{channel_id}/generate", headers=auth_headers(id_token))


def main():
    ok = True

    print("=== Setting up two real Firebase test users ===")
    uid_a, token_a = create_real_test_user("a")
    uid_b, token_b = create_real_test_user("b")
    print(f"✅ Created user A: {uid_a}")
    print(f"✅ Created user B: {uid_b}")

    try:
        # ── Step 1: each user creates their own workspace ───────────────
        print("\n=== Step 1: POST /workspaces for each user ===")
        ws_a = client.post("/workspaces", headers=auth_headers(token_a)).json()
        ws_b = client.post("/workspaces", headers=auth_headers(token_b)).json()
        created_doc_refs.append((WORKSPACES, ws_a["workspace_id"]))
        created_doc_refs.append((WORKSPACES, ws_b["workspace_id"]))
        print(f"✅ User A workspace: {ws_a['workspace_id']}")
        print(f"✅ User B workspace: {ws_b['workspace_id']}")

        # ── Step 2: each user creates their own channel ──────────────────
        print("\n=== Step 2: POST /channels for each user ===")
        channel_payload = {
            "name": "AI carryON (test)",
            "category": "AI, coding, and future technology",
            "language": "en",
            "format": "shorts",
        }
        ch_a = client.post("/channels", json=channel_payload, headers=auth_headers(token_a)).json()
        ch_b = client.post("/channels", json=channel_payload, headers=auth_headers(token_b)).json()
        created_doc_refs.append((CHANNELS, ch_a["channel_id"]))
        created_doc_refs.append((CHANNELS, ch_b["channel_id"]))
        created_doc_refs.append((PROVIDER_KEYS, ch_a["channel_id"]))
        created_doc_refs.append((PROVIDER_KEYS, ch_b["channel_id"]))
        print(f"✅ User A channel: {ch_a['channel_id']}")
        print(f"✅ User B channel: {ch_b['channel_id']}")

        # ── Step 3: each user runs their OWN channel's pipeline for real ─
        print("\n=== Step 3: each user runs POST /channels/{id}/generate (real pipeline, real LLM calls) ===")
        resp_a = asyncio.run(run_channel_generation_via_http(token_a, ch_a["channel_id"]))
        check = resp_a.status_code == 200 and resp_a.json().get("status") == "reviewed"
        print(("✅" if check else "❌"), f"User A's own channel run: {resp_a.status_code}, status={resp_a.json().get('status') if resp_a.status_code == 200 else resp_a.text}")
        ok = ok and check

        resp_b = asyncio.run(run_channel_generation_via_http(token_b, ch_b["channel_id"]))
        check = resp_b.status_code == 200 and resp_b.json().get("status") == "reviewed"
        print(("✅" if check else "❌"), f"User B's own channel run: {resp_b.status_code}, status={resp_b.json().get('status') if resp_b.status_code == 200 else resp_b.text}")
        ok = ok and check

        # ── Step 4: GET /channels never cross-leaks ──────────────────────
        print("\n=== Step 4: GET /channels — no cross-leak ===")
        list_a = client.get("/channels", headers=auth_headers(token_a)).json()
        list_b = client.get("/channels", headers=auth_headers(token_b)).json()
        ids_a = {c["channel_id"] for c in list_a}
        ids_b = {c["channel_id"] for c in list_b}
        check = ch_a["channel_id"] in ids_a and ch_a["channel_id"] not in ids_b
        print(("✅" if check else "❌"), "User A sees their own channel, not User B's")
        ok = ok and check
        check = ch_b["channel_id"] in ids_b and ch_b["channel_id"] not in ids_a
        print(("✅" if check else "❌"), "User B sees their own channel, not User A's")
        ok = ok and check

        # ── Step 5: the negative test — User B against User A's channel ──
        print("\n=== Step 5: negative test — User B's token against User A's channel ===")
        cross_resp = client.post(f"/channels/{ch_a['channel_id']}/generate", headers=auth_headers(token_b))
        check = cross_resp.status_code == 403
        print(
            ("✅" if check else "❌"),
            f"User B against User A's channel correctly gets 403 (got {cross_resp.status_code}: {cross_resp.text[:200]})",
        )
        ok = ok and check

        # ── Step 6: unknown channel_id gets 404, not 403 ──────────────────
        print("\n=== Step 6: unknown channel_id ===")
        unknown_resp = client.post(f"/channels/{uuid.uuid4()}/generate", headers=auth_headers(token_a))
        check = unknown_resp.status_code == 404
        print(("✅" if check else "❌"), f"Unknown channel_id correctly gets 404 (got {unknown_resp.status_code})")
        ok = ok and check

    finally:
        cleanup()

    print("\n" + "=" * 70)
    if ok:
        print("✅ Real Phase 6 end-to-end multi-tenancy verification PASSED.")
    else:
        print("❌ One or more checks FAILED — see ❌ lines above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
