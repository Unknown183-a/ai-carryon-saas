"use client";

/**
 * Ch.12f — "Forgot password", step 2.
 *
 * The link Firebase emails from forgot-password/page.tsx's
 * sendPasswordResetEmail(..., { url: "<origin>/reset-password", handleCodeInApp: true })
 * lands here with `?mode=resetPassword&oobCode=<token>` in the URL —
 * that's what makes this "automatic": the user clicks the email link and
 * is already on this exact form, token in hand, no copy-pasting.
 *
 * The token is only ever verified/consumed on submit (verifyPasswordResetCode
 * + confirmPasswordReset both happen in useAuth().resetPassword), not on
 * page load — some mail clients (Outlook, Gmail's link-scanning bots)
 * prefetch links for safety scanning, which would burn a single-use code
 * before the real user ever saw this page if we validated eagerly.
 *
 * `output: 'export'` (next.config.js) means useSearchParams() must be
 * wrapped in Suspense or the static build fails — hence the two-component
 * split below.
 */
import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const { resetPassword } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const oobCode = searchParams.get("oobCode");
  const mode = searchParams.get("mode");

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const linkLooksValid = mode === "resetPassword" && !!oobCode;

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
      await resetPassword(oobCode as string, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? readableAuthError(err.message) : "Could not reset password.");
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

        {!linkLooksValid ? (
          <>
            <h1 className="font-display text-2xl font-semibold text-paper">Invalid link</h1>
            <p className="mt-3 text-sm text-slate">
              This reset link is missing or malformed. Request a new one below.
            </p>
            <Link href="/forgot-password" className="btn-primary mt-6 inline-block w-full text-center">
              Request a new link
            </Link>
          </>
        ) : done ? (
          <>
            <h1 className="font-display text-2xl font-semibold text-paper">Password updated</h1>
            <p className="mt-3 text-sm text-slate">
              Your password has been changed. Sign in with your new password.
            </p>
            <button
              onClick={() => router.replace("/login")}
              className="btn-primary mt-6 w-full"
            >
              Go to sign in
            </button>
          </>
        ) : (
          <>
            <h1 className="font-display text-2xl font-semibold text-paper">Choose a new password</h1>
            <p className="mt-1 text-sm text-slate">Make it something you haven&apos;t used before.</p>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
              <div>
                <label className="field-label" htmlFor="password">New password</label>
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
                <label className="field-label" htmlFor="confirm">Confirm new password</label>
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
                {submitting ? "Updating…" : "Update password"}
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
  if (message.includes("auth/expired-action-code")) {
    return "This link has expired. Request a new one.";
  }
  if (message.includes("auth/invalid-action-code")) {
    return "This link has already been used or is invalid. Request a new one.";
  }
  if (message.includes("auth/weak-password")) {
    return "That password is too weak.";
  }
  if (message.includes("auth/network-request-failed")) {
    return "Network error — check your connection and try again.";
  }
  return "Something went wrong. Please try again.";
}
