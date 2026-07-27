// Email verification helpers — Firebase Auth
// Drop this into your frontend auth module (adjust the import path for `auth` to match your project).

import { sendEmailVerification } from "firebase/auth";

const VERIFIED_REDIRECT_URL = "https://yourapp.com/verified"; // TODO: replace with real domain
const RESEND_COOLDOWN_MS = 60 * 1000; // 60s client-side throttle

let lastResendAt = 0;

/**
 * Send (or resend) the verification email to the given Firebase user.
 * Call this immediately after signup, and again from the "resend" button.
 */
export async function triggerVerificationEmail(user) {
  const now = Date.now();
  if (now - lastResendAt < RESEND_COOLDOWN_MS) {
    const waitSec = Math.ceil((RESEND_COOLDOWN_MS - (now - lastResendAt)) / 1000);
    throw new Error(`Please wait ${waitSec}s before requesting another email.`);
  }
  lastResendAt = now;
  await sendEmailVerification(user, { url: VERIFIED_REDIRECT_URL });
}

/**
 * Poll the user's verification status every few seconds.
 * Calls onVerified() once emailVerified flips to true, then stops.
 * Returns a cancel function so the caller can clear it on unmount.
 */
export function pollForVerification(user, onVerified, intervalMs = 3000) {
  const interval = setInterval(async () => {
    await user.reload();
    if (user.emailVerified) {
      clearInterval(interval);
      onVerified();
    }
  }, intervalMs);

  return () => clearInterval(interval);
}

/**
 * Call this at login. Returns true if the user is allowed into the app,
 * false if they need to be shown the "check your inbox" screen instead.
 */
export async function isVerifiedForLogin(user) {
  await user.reload();
  return user.emailVerified === true;
}
