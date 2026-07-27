"use client";

/**
 * Ch.12f — "Forgot password", step 1.
 *
 * Takes only an email. On submit we always show the same success
 * message, whether or not that email belongs to a real account — never
 * "no account found for that email" here. That's what stops this form
 * from being usable to enumerate registered users. The actual
 * enumeration protection happens at the Firebase project level (Console
 * → Authentication → Settings → User actions → Email enumeration
 * protection); this page just makes sure it never re-introduces the leak
 * on the frontend by branching on auth/user-not-found.
 */
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export default function ForgotPasswordPage() {
  const { forgotPassword } = useAuth();
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await forgotPassword(email);
    } catch (err) {
      // Only genuinely unrecoverable, non-identity-revealing failures
      // surface here (bad email format, rate limited, network error).
      // auth/user-not-found is deliberately treated the same as success.
      const message = err instanceof Error ? err.message : "";
      if (!message.includes("auth/user-not-found")) {
        setError(readableAuthError(message));
        setSubmitting(false);
        return;
      }
    }
    // Same UI outcome whether the email existed or not.
    setSent(true);
    setSubmitting(false);
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

        {sent ? (
          <>
            <h1 className="font-display text-2xl font-semibold text-paper">Check your email</h1>
            <p className="mt-3 text-sm text-slate">
              If an account exists for <span className="text-paper">{email}</span>, we&apos;ve
              sent a link to reset the password. It&apos;s valid for a short while, so use it
              soon — you can always request a new one from here.
            </p>
          </>
        ) : (
          <>
            <h1 className="font-display text-2xl font-semibold text-paper">Reset your password</h1>
            <p className="mt-1 text-sm text-slate">
              Enter the email on your account and we&apos;ll send you a reset link.
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
                {submitting ? "Sending…" : "Send reset link"}
              </button>
            </form>
          </>
        )}

        <p className="mt-6 text-center text-sm text-slate">
          <Link href="/login" className="font-medium text-signal hover:underline">
            Back to sign in
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
  if (message.includes("auth/network-request-failed")) {
    return "Network error — check your connection and try again.";
  }
  return "Something went wrong. Please try again.";
}
