"""
Phase 1 — Firebase Auth + Firestore throwaway test script.

What this proves (per BUILD_GUIDE.md Phase 1 Definition of Done):
1. A user can be created via Firebase Auth.
2. A Firestore document can be written and read back for that user.
3. A DIFFERENT (fake) uid is denied by the security rules — the negative test.

Run with:
    python phase1_firebase_test.py

Requires .env in the project root with:
    FIREBASE_PROJECT_ID=...
    FIREBASE_SERVICE_ACCOUNT_JSON=<base64-encoded service account JSON>
"""

import base64
import json
import os
import uuid

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import auth, credentials, firestore

# ── Load .env from project root ────────────────────────────────────────────
load_dotenv()

PROJECT_ID = os.environ["FIREBASE_PROJECT_ID"]
SERVICE_ACCOUNT_B64 = os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"]

# ── Decode the base64 service account JSON and init the Admin SDK ─────────
service_account_info = json.loads(base64.b64decode(SERVICE_ACCOUNT_B64))
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred, {"projectId": PROJECT_ID})

db = firestore.client()

# ── 1. Create a test user via Firebase Auth ────────────────────────────────
test_email = f"phase1-test-{uuid.uuid4().hex[:8]}@example.com"
test_password = "TestPassword123!"

print(f"Creating test user: {test_email}")
user = auth.create_user(email=test_email, password=test_password)
uid = user.uid
print(f"✅ Created user with uid: {uid}")

# ── 2. Write a document to users/{uid} ─────────────────────────────────────
doc_ref = db.collection("users").document(uid)
doc_ref.set({
    "uid": uid,
    "email": test_email,
    "createdBy": "phase1_test_script",
})
print(f"✅ Wrote document to users/{uid}")

# ── 3. Read it back ─────────────────────────────────────────────────────────
snapshot = doc_ref.get()
if snapshot.exists and snapshot.to_dict().get("uid") == uid:
    print(f"✅ Read back document: {snapshot.to_dict()}")
else:
    print("❌ FAILED: document did not read back correctly")

# ── 4. Negative test note ───────────────────────────────────────────────────
# The Admin SDK (used above) bypasses Firestore security rules entirely —
# that's expected, it's how backends are supposed to work. To actually test
# that a MISMATCHED uid is denied, you need to simulate a CLIENT request,
# which respects rules. The Admin SDK can't do that directly, so below we
# use the REST API with a real ID token instead — this is what actually
# exercises your firestore.rules.

import requests

print("\n--- Negative test: wrong uid should be denied ---")

# Mint a custom token for our test user, then exchange it for an ID token
# using the Firebase Auth REST API (this simulates what a real client does).
FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY")

if not FIREBASE_WEB_API_KEY:
    print(
        "⚠️  FIREBASE_WEB_API_KEY not set in .env — skipping the live rules "
        "negative test. Add it (Firebase console → Project settings → General "
        "→ Web API Key) to fully complete this test."
    )
else:
    custom_token = auth.create_custom_token(uid).decode("utf-8")

    exchange_url = (
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"
        f"?key={FIREBASE_WEB_API_KEY}"
    )
    resp = requests.post(exchange_url, json={"token": custom_token, "returnSecureToken": True})
    id_token = resp.json()["idToken"]

    # Try to read a DIFFERENT user's document — should be denied by rules
    fake_uid = "definitely-not-" + uid
    fake_doc_ref = db.collection("users").document(fake_uid)
    fake_doc_ref.set({"uid": fake_uid, "email": "attacker@example.com"})

    firestore_rest_url = (
        f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}"
        f"/databases/(default)/documents/users/{fake_uid}"
    )
    headers = {"Authorization": f"Bearer {id_token}"}
    r = requests.get(firestore_rest_url, headers=headers)

    if r.status_code == 403 or r.status_code == 401:
        print(f"✅ Correctly denied (status {r.status_code}) — rules are working")
    else:
        print(f"❌ FAILED: expected 401/403, got {r.status_code}: {r.text}")

    # Clean up the fake doc (using Admin SDK, which bypasses rules)
    fake_doc_ref.delete()

# ── 5. Cleanup ───────────────────────────────────────────────────────────────
print("\nCleaning up test user and document...")
doc_ref.delete()
auth.delete_user(uid)
print("✅ Cleanup complete")

print("\n🎉 Phase 1 test script finished.")
