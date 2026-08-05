"""
Firebase Admin SDK initialization.

Reads FIREBASE_PROJECT_ID and FIREBASE_SERVICE_ACCOUNT_JSON (base64-encoded)
from environment variables and initializes the firebase_admin app exactly
once, no matter how many times init_firebase() is called.

Also wires up the Storage bucket option (FIREBASE_STORAGE_BUCKET, falling
back to the project's default `<project_id>.appspot.com` bucket if unset)
so `app/workers/storage.py` can resolve `firebase_admin.storage.bucket()`
against this same app without a second `initialize_app()` call — Auth,
Firestore, and Storage all share one Firebase Admin app, same as any
single-project Firebase setup.
"""

import base64
import json
import os

import firebase_admin
from firebase_admin import credentials

_initialized = False


def init_firebase() -> None:
    global _initialized
    if _initialized or firebase_admin._apps:
        _initialized = True
        return

    project_id = os.environ["FIREBASE_PROJECT_ID"]
    service_account_b64 = os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"]

    service_account_info = json.loads(base64.b64decode(service_account_b64))
    cred = credentials.Certificate(service_account_info)

    storage_bucket = os.environ.get("FIREBASE_STORAGE_BUCKET") or f"{project_id}.appspot.com"

    firebase_admin.initialize_app(cred, {"projectId": project_id, "storageBucket": storage_bucket})
    _initialized = True
