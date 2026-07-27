// Signup handler — creates the account, then gates on email verification.
// Adjust the `auth` import to wherever your Firebase app is initialized.

import { createUserWithEmailAndPassword } from "firebase/auth";
import { auth } from "../firebase"; // TODO: adjust path if your init file lives elsewhere
import { triggerVerificationEmail } from "./emailVerification";

/**
 * @param {string} email
 * @param {string} password
 * @param {(email: string) => void} showCheckInboxScreen - render the holding screen, not the dashboard
 */
export async function handleSignup(email, password, showCheckInboxScreen) {
  const { user } = await createUserWithEmailAndPassword(auth, email, password);
  await triggerVerificationEmail(user);
  showCheckInboxScreen(email);
  return user;
}
