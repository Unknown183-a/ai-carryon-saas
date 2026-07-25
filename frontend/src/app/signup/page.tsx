"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function SignupPage() {
  const { signUp } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Password needs at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }

    setSubmitting(true);
    try {
      await signUp(email, password);
      // Ch.12c: workspace creation happens automatically in AuthProvider
      // the moment onAuthStateChanged sees this new user.
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? readableAuthError(err.message) : "Could not create account.");
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

        <h1 className="font-display text-2xl font-semibold text-paper">Create your account</h1>
        <p className="mt-1 text-sm text-slate">One workspace, run as many channels as you need.</p>

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
            <label className="field-label" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              required
              autoComplete="new-password"
              className="field-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
            />
          </div>
          <div>
            <label className="field-label" htmlFor="confirm">Confirm password</label>
            <input
              id="confirm"
              type="password"
              required
              autoComplete="new-password"
              className="field-input"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="rounded-md border border-danger/30 bg-dangerDim px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          <button type="submit" disabled={submitting} className="btn-primary w-full">
            {submitting ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-signal hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

function readableAuthError(message: string): string {
  if (message.includes("auth/email-already-in-use")) {
    return "An account with that email already exists.";
  }
  if (message.includes("auth/weak-password")) {
    return "That password is too weak.";
  }
  if (message.includes("auth/invalid-email")) {
    return "That email address doesn't look right.";
  }
  return message;
}
