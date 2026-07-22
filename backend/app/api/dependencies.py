"""
Depends() providers — reusable pieces any router can request.

get_current_user: verifies the Firebase JWT and returns the decoded token
  (contains uid, email, etc). Raises 401 if missing/invalid.
get_firestore: returns a shared Firestore client instance.
"""

from fastapi import Depends, HTTPException, Request
from firebase_admin import auth as firebase_auth
from google.cloud.firestore import Client

from app.api.middleware.auth import init_firebase


def get_current_user(request: Request) -> dict:
    """Extracts and verifies the Bearer token from the Authorization header."""
    init_firebase()  # ensures firebase_admin app is initialized exactly once

    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.split("Bearer ", 1)[1]

    try:
        decoded_token = firebase_auth.verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return decoded_token


def get_firestore() -> Client:
    """Returns a Firestore client. Firebase app must already be initialized."""
    init_firebase()
    from firebase_admin import firestore
    return firestore.client()
