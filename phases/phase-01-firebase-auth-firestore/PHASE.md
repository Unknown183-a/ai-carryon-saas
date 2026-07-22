<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 1 — Firebase Auth + Firestore
*(SAD reference: Chapter 12 — Firebase & Firestore)*

**Goal:** a user can be created via Firebase Auth, and a Firestore document can be written and read back, respecting security rules.

**Depends on:** Phase 0.

**Tasks:**
- [x] Enable Email/Password sign-in method in Firebase console
- [x] Create Firestore in Native mode
- [x] Create empty collections: `users`, `projects`, `channels`, `videos`, `analytics`, `schedules`, `settings` (Ch.12)
- [x] Write `firestore.rules` enforcing `request.auth.uid` membership on every read/write (Ch.12e) — **do this now, not later**
- [x] Deploy rules: `firebase deploy --only firestore:rules`
- [x] Download service account JSON, store as `FIREBASE_SERVICE_ACCOUNT_JSON` (base64-encoded) in `.env`
- [x] Write a throwaway test script that: creates a test user, writes one document to `users/{uid}`, reads it back, confirms a *different* fake uid is denied by the rules

**Definition of Done:** the throwaway test script passes, including the negative test (wrong uid is rejected).

**Handoff Notes:**
> Phase 1 completed 2026-07-22 by Amit. Email/Password auth enabled, Firestore created in asia-south1, firestore.rules deployed enforcing uid ownership, service account key stored in .env, throwaway test script (tests/phase1_firebase_test.py) passes including the negative rules test (403 on mismatched uid).

---
