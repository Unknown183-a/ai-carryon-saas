// Login handler — signs in, then blocks unverified users from the dashboard.

import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "../firebase"; // TODO: adjust path if your init file lives elsewhere
import { isVerifiedForLogin } from "./emailVerification";

/**
 * @param {string} email
 * @param {string} password
 * @param {(email: string) => void} showCheckInboxScreen
 * @param {() => void} redirectToDashboard
 */
export async function handleLogin(email, password, showCheckInboxScreen, redirectToDashboard) {
  const { user } = await signInWithEmailAndPassword(auth, email, password);

  if (!(await isVerifiedForLogin(user))) {
    showCheckInboxScreen(email);
    return user;
  }

  redirectToDashboard();
  return user;
}
