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
  signOut as firebaseSignOut,
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

  return (
    <AuthContext.Provider
      value={{ user, workspace, loading, error, signIn, signUp, signOut }}
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
