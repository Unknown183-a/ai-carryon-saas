<!-- Self-contained phase brief. Companion docs: ../../docs/BUILD_GUIDE.md (full build order) and ../../docs/AI-CarryON-Architecture-Document.html (the why). -->

## Phase 1 — Firebase Auth + Firestore
*(SAD reference: Chapter 12 — Firebase & Firestore)*

**Goal:** a user can be created via Firebase Auth, and a Firestore document can be written and read back, respecting security rules.

**Depends on:** Phase 0.

**Tasks:**
- [ ] Enable Email/Password sign-in method in Firebase console
- [ ] Create Firestore in Native mode
- [ ] Create empty collections: `users`, `projects`, `channels`, `videos`, `analytics`, `schedules`, `settings` (Ch.12)
- [ ] Write `firestore.rules` enforcing `request.auth.uid` membership on every read/write (Ch.12e) — **do this now, not later**
- [ ] Deploy rules: `firebase deploy --only firestore:rules`
- [ ] Download service account JSON, store as `FIREBASE_SERVICE_ACCOUNT_JSON` (base64-encoded) in `.env`
- [ ] Write a throwaway test script that: creates a test user, writes one document to `users/{uid}`, reads it back, confirms a *different* fake uid is denied by the rules

**Definition of Done:** the throwaway test script passes, including the negative test (wrong uid is rejected).

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---
