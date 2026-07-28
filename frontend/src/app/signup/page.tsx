"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export default function SignupPage() {
  const { sendSignupLink } = useAuth();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [linkSent, setLinkSent] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await sendSignupLink(email);
      setLinkSent(true);
    } catch (err) {
      setError(err instanceof Error ? readableAuthError(err.message) : "Could not send the link.");
    } finally {
      setSubmitting(false);
    }
  }

  if (linkSent) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-sm text-center">
          <div className="mb-8 flex items-center justify-center gap-2.5">
            <span className="h-2.5 w-2.5 animate-pulseSignal rounded-full bg-signal" />
            <span className="font-display text-sm font-semibold tracking-wide text-slate">
              AI CARRYON
            </span>
          </div>

          <h1 className="font-display text-2xl font-semibold text-paper">Check your inbox</h1>
          <p className="mt-2 text-sm text-slate">
            We sent a link to <span className="font-medium text-paper">{email}</span>. Click it
            and you&apos;ll be brought straight back here to finish setting up your account.
          </p>

          <button
            type="button"
            onClick={() => setLinkSent(false)}
            className="mt-6 text-sm text-slate hover:underline"
          >
            Wrong email? Go back
          </button>
        </div>
      </div>
    );
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
        <p className="mt-1 text-sm text-slate">
          We&apos;ll email you a link to confirm it&apos;s really you — no password needed yet.
        </p>

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

          {error && (
            <p className="rounded-md border border-danger/30 bg-dangerDim px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          <button type="submit" disabled={submitting} className="btn-primary w-full">
            {submitting ? "Sending link…" : "Send verification link"}
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
  if (message.includes("auth/invalid-email")) {
    return "That email address doesn't look right.";
  }
  if (message.includes("auth/too-many-requests")) {
    return "Too many attempts. Wait a moment and try again.";
  }
  return message;
}
