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
  sendPasswordResetEmail,
  confirmPasswordReset,
  verifyPasswordResetCode,
  signOut as firebaseSignOut,
  type ActionCodeSettings,
  type User,
} from "firebase/auth";
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
    await createUserWithEmailAndPassword(getFirebaseAuth(), email, password);
  }

  async function signOut() {
    await firebaseSignOut(getFirebaseAuth());
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
