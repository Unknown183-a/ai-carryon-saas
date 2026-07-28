"use client";

/**
 * Wraps Firebase's auth state in a context so any screen can read the
 * current user and (via ApiClient) an always-fresh ID token.
 *
 * Ch.12c: a Workspace should exist the moment auth succeeds. There's no
 * Cloud Function wired up for that yet (see workspaces.py's docstring),
 * so the pragmatic equivalent lives here — once we see a signed-in user,
 * call POST /workspaces. It's idempotent server-side, so firing it on
 * every sign-in (not just the first ever) is safe and simple.
 */
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  sendPasswordResetEmail,
  confirmPasswordReset,
  verifyPasswordResetCode,
  sendSignInLinkToEmail,
  isSignInWithEmailLink,
  signInWithEmailLink,
  updatePassword,
  signOut as firebaseSignOut,
  type ActionCodeSettings,
  type User,
} from "firebase/auth";

// Ch.12i — key used to remember the address a signup link was sent to,
// since Firebase's signInWithEmailLink() needs the email again once the
// link is clicked (same-device flow; see completeSignupWithLink for the
// cross-device fallback where this is missing).
const PENDING_SIGNUP_EMAIL_KEY = "ai-carryon:pendingSignupEmail";
import { getFirebaseAuth } from "@/lib/firebase";
import { apiFetch } from "@/lib/api";

type Workspace = {
  workspace_id: string;
  [key: string]: unknown;
};

type AuthContextValue = {
  user: User | null;
  workspace: Workspace | null;
  loading: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** Ch.12g — email verification. Fired automatically right after
   * signUp(); exposed separately too so the "check your inbox" screen
   * can offer a "resend" button without re-running signup. */
  resendVerificationEmail: () => Promise<void>;
  /** Ch.12i — passwordless signup. No account exists yet at this point;
   * Firebase just emails a sign-in link. Nothing is created until the
   * user actually clicks it, so a typo'd email here creates nothing at
   * all — there's no stuck/unverified account left behind to clean up. */
  sendSignupLink: (email: string) => Promise<void>;
  /** Ch.12i — call this on the page the emailed link points at. Verifies
   * the link, creates+signs in the account (this IS account creation —
   * clicking the link is the proof of ownership), and returns the user
   * so the caller can move on to collecting a password. Throws if the
   * link is invalid/expired, or if the email can't be recovered (see
   * needsEmailForSignupLink below) and none was supplied. */
  completeSignupWithLink: (url: string, emailOverride?: string) => Promise<User>;
  /** True if the current URL is a valid signup link but we don't have
   * the email stored locally to complete it with (e.g. link opened on a
   * different device/browser than it was requested from) — the caller
   * should prompt for the email and pass it to completeSignupWithLink. */
  needsEmailForSignupLink: (url: string) => boolean;
  /** Ch.12i — second half of passwordless signup: the account exists
   * (verified, signed in via the link) but has no password yet. Sets
   * one so future logins can use signIn() normally. */
  setInitialPassword: (password: string) => Promise<void>;
  /** Ch.12f — "Forgot password". Always resolves the same way whether or
   * not the email is registered; Firebase's own enumeration-protection
   * setting (Console → Authentication → Settings → User actions) is what
   * makes that true at the network level, not this function. */
  forgotPassword: (email: string) => Promise<void>;
  /** Ch.12f — second half of the flow: verifies the oobCode from the
   * emailed link is still valid, then sets the new password. Throws if
   * the code is invalid/expired/already used. */
  resetPassword: (oobCode: string, newPassword: string) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// Ch.12g — where the verification link (hosted on Firebase's own action
// page) sends the user once they've clicked it and it's been applied.
function verificationActionCodeSettings(): ActionCodeSettings {
  return {
    url: `${window.location.origin}/login?verified=1`,
    handleCodeInApp: false,
  };
}

// Ch.12i — handleCodeInApp: true here on purpose: unlike the old
// verification link, THIS click has to land back in our own app (not
// Firebase's hosted page), because completing sign-in and then setting a
// password both have to run as real code, not just a "you're verified"
// message.
function signupLinkActionCodeSettings(): ActionCodeSettings {
  return {
    url: `${window.location.origin}/complete-signup`,
    handleCodeInApp: true,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(getFirebaseAuth(), async (nextUser) => {
      setUser(nextUser);
      setError(null);

      if (nextUser) {
        try {
          const ws = await apiFetch<Workspace>("/workspaces", { method: "POST" });
          setWorkspace(ws);
        } catch (err) {
          // Not fatal to being signed in — surfaced so the dashboard can
          // show a real error instead of silently having no workspace.
          setError(err instanceof Error ? err.message : "Could not reach the workspace.");
        }
      } else {
        setWorkspace(null);
      }

      setLoading(false);
    });

    return unsubscribe;
  }, []);

  async function signIn(email: string, password: string) {
    setError(null);
    await signInWithEmailAndPassword(getFirebaseAuth(), email, password);
  }

  async function signUp(email: string, password: string) {
    setError(null);
    const { user: newUser } = await createUserWithEmailAndPassword(getFirebaseAuth(), email, password);
    // Ch.12g — fire the verification email as part of signup itself, not
    // as a separate step the caller has to remember.
    await sendEmailVerification(newUser, verificationActionCodeSettings());
  }

  async function signOut() {
    await firebaseSignOut(getFirebaseAuth());
  }

  async function resendVerificationEmail() {
    setError(null);
    const current = getFirebaseAuth().currentUser;
    if (!current) {
      throw new Error("You need to be signed in to resend a verification email.");
    }
    await sendEmailVerification(current, verificationActionCodeSettings());
  }

  async function sendSignupLink(email: string) {
    setError(null);
    await sendSignInLinkToEmail(getFirebaseAuth(), email, signupLinkActionCodeSettings());
    // Same-device convenience: signInWithEmailLink needs the email again.
    // If they open the link on a different device/browser, it won't be
    // here — completeSignupWithLink's caller handles that via
    // needsEmailForSignupLink + a manual prompt.
    window.localStorage.setItem(PENDING_SIGNUP_EMAIL_KEY, email);
  }

  function needsEmailForSignupLink(url: string): boolean {
    if (!isSignInWithEmailLink(getFirebaseAuth(), url)) return false;
    return !window.localStorage.getItem(PENDING_SIGNUP_EMAIL_KEY);
  }

  async function completeSignupWithLink(url: string, emailOverride?: string): Promise<User> {
    setError(null);
    if (!isSignInWithEmailLink(getFirebaseAuth(), url)) {
      throw new Error("That link is invalid or has already been used.");
    }
    const email = emailOverride ?? window.localStorage.getItem(PENDING_SIGNUP_EMAIL_KEY);
    if (!email) {
      throw new Error("We need your email to finish this — please enter it below.");
    }
    const { user: newUser } = await signInWithEmailLink(getFirebaseAuth(), email, url);
    window.localStorage.removeItem(PENDING_SIGNUP_EMAIL_KEY);
    return newUser;
  }

  async function setInitialPassword(password: string) {
    setError(null);
    const current = getFirebaseAuth().currentUser;
    if (!current) {
      throw new Error("You need to be signed in to set a password.");
    }
    await updatePassword(current, password);
  }

  async function forgotPassword(email: string) {
    setError(null);
    // handleCodeInApp: true — the emailed link lands the user directly
    // back on THIS app's /reset-password page (with ?oobCode=... in the
    // URL) instead of Firebase's own hosted default action page. That's
    // the "automatically come back to our UI" behavior.
    const actionCodeSettings: ActionCodeSettings = {
      url: `${window.location.origin}/reset-password`,
      handleCodeInApp: true,
    };
    await sendPasswordResetEmail(getFirebaseAuth(), email, actionCodeSettings);
  }

  async function resetPassword(oobCode: string, newPassword: string) {
    setError(null);
    // Throws (invalid/expired/used code) before ever touching the
    // password — same "verify identity, then act" order described in
    // Ch.12f. Getting the email back here also lets the reset-password
    // page show "resetting password for you@studio.com" if you want it.
    await verifyPasswordResetCode(getFirebaseAuth(), oobCode);
    await confirmPasswordReset(getFirebaseAuth(), oobCode, newPassword);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        workspace,
        loading,
        error,
        signIn,
        signUp,
        signOut,
        resendVerificationEmail,
        sendSignupLink,
        completeSignupWithLink,
        needsEmailForSignupLink,
        setInitialPassword,
        forgotPassword,
        resetPassword,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
