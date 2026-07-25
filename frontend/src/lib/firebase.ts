/**
 * Firebase client SDK — Phase 1's Auth, from the browser side.
 * The backend (app/api/middleware/auth.py) verifies tokens with the
 * Admin SDK; this file only ever produces them.
 *
 * Initialization is lazy (getFirebaseAuth(), not a top-level `export
 * const auth = ...`) on purpose: a top-level call runs the instant this
 * module is imported, including during `next build`'s server-side
 * prerender pass — before any browser, and before NEXT_PUBLIC_* env vars
 * are necessarily real, ever get involved. These auth screens have no
 * reason to be prerendered anyway (fully client-rendered, gated on
 * client-side auth state), so the real fix is: never touch Firebase
 * outside a useEffect/event handler, which only ever run in the browser.
 */
import { initializeApp, getApps, getApp, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

let cachedApp: FirebaseApp | undefined;
let cachedAuth: Auth | undefined;

function getFirebaseApp(): FirebaseApp {
  if (!cachedApp) {
    cachedApp = getApps().length ? getApp() : initializeApp(firebaseConfig);
  }
  return cachedApp;
}

/** Call this only from a useEffect, event handler, or other browser-only
 * code path — never from a component's top-level render body. */
export function getFirebaseAuth(): Auth {
  if (!cachedAuth) {
    cachedAuth = getAuth(getFirebaseApp());
  }
  return cachedAuth;
}
