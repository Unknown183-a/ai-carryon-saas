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
- [x] Forgot password flow (Ch.12f) — `forgotPassword()`/`resetPassword()` in `auth-context.tsx`; always resolves the same way regardless of whether the email is registered (email enumeration protection enabled in Firebase console)
- [x] Email verification on signup (Ch.12g) — `signUp()` calls `sendEmailVerification()`; new `/verify-email` holding screen polls `emailVerified` and redirects to `/dashboard` once true; login re-checks `emailVerified` on every sign-in, not just signup
- [x] Mistyped-email recovery (Ch.12h) — "Wrong email? Start over" on `/verify-email` deletes the unverified account (`deleteUser`) and returns to `/signup`, since an unverified account has no real data attached to it yet

**Definition of Done:** the throwaway test script passes, including the negative test (wrong uid is rejected). Email verification and password reset both work end-to-end: an unverified account cannot reach `/dashboard` via signup or login, and a password reset email is only ever sent to a real, owned inbox.

**Handoff Notes:**
> Phase 1 completed 2026-07-22 by Amit. Email/Password auth enabled, Firestore created in asia-south1, firestore.rules deployed enforcing uid ownership, service account key stored in .env, throwaway test script (tests/phase1_firebase_test.py) passes including the negative rules test (403 on mismatched uid).

> Update 2026-07-27 by Amit. Added email verification gate (signup → /verify-email holding screen → poll → /dashboard; login re-checks emailVerified) and a "start over" option for mistyped emails on signup, since an unverified/undeliverable email previously had no recovery path. Forgot-password flow already existed from Ch.12f; both now share the same "prove inbox ownership via a link" model. Still pending: custom SMTP domain for Firebase auth emails (currently sending from shared firebaseapp.com, which can land in spam) and re-authentication handling for auth/requires-recent-login on account deletion.

---
