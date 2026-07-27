"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { getFirebaseAuth } from "@/lib/firebase";

export default function LoginPage() {
  const { signIn } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn(email, password);
      // Ch.12g — signIn() succeeding just means the credentials were
      // right; it says nothing about email verification. Check the flag
      // directly off the freshly-signed-in Firebase user before deciding
      // where to send them.
      const current = getFirebaseAuth().currentUser;
      if (current && !current.emailVerified) {
        router.replace("/verify-email");
      } else {
        router.replace("/dashboard");
      }
    } catch (err) {
      setError(err instanceof Error ? readableAuthError(err.message) : "Sign in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-2.5">
          <span className="h-2.5 w-2.5 animate-pulseSignal rounded-full bg-signal" />
          <span className="font-display text-sm font-semibold tracking-wide text-slate">
            AI CARRYON
          </span>
        </div>

        <h1 className="font-display text-2xl font-semibold text-paper">Sign in</h1>
        <p className="mt-1 text-sm text-slate">Mission control for your channels.</p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label className="field-label" htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              className="field-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@studio.com"
            />
          </div>
          <div>
            <div className="flex items-center justify-between">
              <label className="field-label" htmlFor="password">Password</label>
              <Link href="/forgot-password" className="text-sm text-signal hover:underline">
                Forgot password?
              </Link>
            </div>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              className="field-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="rounded-md border border-danger/30 bg-dangerDim px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          <button type="submit" disabled={submitting} className="btn-primary w-full">
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate">
          New here?{" "}
          <Link href="/signup" className="font-medium text-signal hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}

function readableAuthError(message: string): string {
  if (message.includes("auth/invalid-credential") || message.includes("auth/wrong-password")) {
    return "That email and password don't match.";
  }
  if (message.includes("auth/user-not-found")) {
    return "No account found for that email.";
  }
  if (message.includes("auth/too-many-requests")) {
    return "Too many attempts. Wait a moment and try again.";
  }
  return message;
}
