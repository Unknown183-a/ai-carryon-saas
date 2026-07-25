Owned by: **Phase 11 — frontend-dashboard**

See `../phases/phase-11-frontend-dashboard/PHASE.md` for the phase brief this implements.

# AI CarryON — Frontend

Next.js 14 (App Router) + TypeScript + Tailwind. Talks to the Phase 2/6/7
FastAPI gateway and Phase 1's Firebase Auth directly — no server-side
Next.js API routes, the browser calls the gateway itself.

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local   # fill in Firebase web config + API base URL
npm run dev
```

Needs the backend running (`uvicorn app.api.main:app --reload` from
`backend/`, per `docker/README.md` / `BUILD_GUIDE.md` Phase 2) reachable
at `NEXT_PUBLIC_API_BASE_URL`.

## What's here (Phase 11 checklist)

- [x] Next.js app in `frontend/`
- [x] Login / Sign Up screens against Firebase Auth
- [x] Workspace dashboard nav (Ch.12c's list: Dashboard, Channels, Analytics,
      Billing, API Providers, Team, Settings, Logs)
- [x] Create-Channel form matching Ch.12d's fields exactly (`src/lib/types.ts`
      mirrors `backend/app/models/channel.py` field-for-field)
- [x] Live status view — polls `/health` (Ch.03's `WS /ws/pipeline/{run_id}`
      doesn't exist on the backend yet, so this polls rather than sockets;
      swap it in later without touching anything else on the page, see the
      comment in `channels/[id]/page.tsx`)
- [x] Provider connection screens with the "encrypted and scoped to this
      channel only" messaging — but see the note below, this one's honest
      about a real gap

**Known gap, called out on the Providers page itself:** the backend only
*accepts* provider keys at channel creation. There's no
`GET/PATCH /channels/{id}/provider-keys` route, and by design the backend
never returns decrypted keys — so today you can't see which keys are set
on an existing channel or rotate one without recreating the channel. That's
a backend task, not a frontend one; flagging it here per the repo's own
handoff rule instead of quietly working around it.

## Structure

```
src/
  app/
    login/, signup/            — public auth screens
    (dashboard)/                — everything behind the auth guard
      layout.tsx                 — sidebar + redirect-if-signed-out
      dashboard/                 — overview: gateway health + channel summary
      channels/                  — list, [id] detail + live status, new (create form)
      providers/, analytics/, billing/, team/, settings/, logs/
  components/                  — Sidebar, StatusDot, ComingSoon
  lib/
    firebase.ts                  — client SDK init
    auth-context.tsx             — auth state + calls POST /workspaces on sign-in (Ch.12c)
    api.ts                       — fetch wrapper, attaches Firebase ID token
    types.ts                     — mirrors backend Pydantic models
```

## Design direction

Dark "broadcast ops desk" look — the product runs channels autonomously,
so the frontend reads like a control room watching them, not a generic
SaaS marketing template. Amber = the one on-air action color (primary
buttons, active nav). Cyan/teal ("signal") is reserved only for genuinely
live/running state — it never appears decoratively, so when it's on
screen it always means something is actually happening right now.

## Definition of Done (per PHASE.md)

> a brand-new user, using only the UI, can go from signup to a channel
> with `status: ready`

Verified path: `/signup` → auth succeeds → workspace auto-created →
`/dashboard` → "+ New channel" → fill the form → `POST /channels` returns
`status: "ready"` (Channel Factory, Ch.12d) → redirected to
`/channels/{id}` showing that status live.
