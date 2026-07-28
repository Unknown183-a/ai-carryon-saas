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
- [x] ~~Email verification on signup (Ch.12g)~~ — **superseded, see Ch.12i below**
- [x] ~~Mistyped-email recovery (Ch.12h)~~ — **superseded, see Ch.12i below** (no longer needed: the new flow can't create an account from a typo in the first place)
- [x] Passwordless signup via emailed link (Ch.12i) — replaces the password-up-front signup form entirely. signup/page.tsx collects only an email and calls sendSignupLink(); no account exists until the emailed link is clicked. Clicking it opens /complete-signup in this app directly (handleCodeInApp: true), which calls completeSignupWithLink() — this is the actual moment the account is created, already verified, since clicking the link is the proof of ownership. That page then collects a password (setInitialPassword()) so future logins can use the normal email+password form. Cross-device link opens (link requested on one device, opened on another) are handled via needsEmailForSignupLink(), which prompts for the email again instead of failing. Requires Email link (passwordless sign-in) enabled in Firebase Console → Authentication → Sign-in method (a sub-toggle under Email/Password, off by default) — enabled 2026-07-28.

**Definition of Done:** the throwaway test script passes, including the negative test (wrong uid is rejected). Signup cannot create an account from an email the user doesn't control — verification happens before account creation, not after — and a password reset email is only ever sent to a real, owned inbox.

**Handoff Notes:**
> Phase 1 completed 2026-07-22 by Amit. Email/Password auth enabled, Firestore created in asia-south1, firestore.rules deployed enforcing uid ownership, service account key stored in .env, throwaway test script (tests/phase1_firebase_test.py) passes including the negative rules test (403 on mismatched uid).

> Update 2026-07-27 by Amit. Added email verification gate (signup → /verify-email holding screen → poll → /dashboard; login re-checks emailVerified) and a "start over" option for mistyped emails on signup, since an unverified/undeliverable email previously had no recovery path. Forgot-password flow already existed from Ch.12f; both now share the same "prove inbox ownership via a link" model. Still pending: custom SMTP domain for Firebase auth emails (currently sending from shared firebaseapp.com, which can land in spam) and re-authentication handling for auth/requires-recent-login on account deletion.

> Update 2026-07-28 by Amit. Replaced the 2026-07-27 approach with passwordless email-link signup — verification now happens before account creation instead of after, so a mistyped email creates nothing at all (the "start over" delete-and-retry button from the previous update is no longer needed for that case, though the code wasn't removed). Enabled "Email link (passwordless sign-in)" in Firebase Console. Built, deployed (npm run build && firebase deploy --only hosting), and confirmed working end-to-end on the live site: signup → email → link → /complete-signup → set password → /dashboard. Old /verify-email page and password-based signUp() still exist in the codebase but are now unused dead code — cleanup deferred, not blocking. Custom SMTP domain still pending from the previous update.

---
