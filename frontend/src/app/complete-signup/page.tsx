"use client";

/**
 * Ch.12i — this is where the emailed link actually lands. Clicking the
 * link IS the redirect back to our UI; nothing manual happens on the
 * user's end beyond that one click. Two things happen here, in order:
 *
 *   1. Verify the link + create/sign in the account (completeSignupWithLink).
 *      This is the moment the account is actually created — a typo'd
 *      email upstream in signup/page.tsx never reaches this point at
 *      all, since nothing was created there in the first place.
 *   2. Ask for a password, so future logins can use the normal
 *      email+password form instead of requesting a new link every time.
 */
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

type Stage = "completing" | "need-email" | "set-password" | "error";

export default function CompleteSignupPage() {
  const { completeSignupWithLink, needsEmailForSignupLink, setInitialPassword } = useAuth();
  const router = useRouter();

  const [stage, setStage] = useState<Stage>("completing");
  const [manualEmail, setManualEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const url = window.location.href;

    if (needsEmailForSignupLink(url)) {
      setStage("need-email");
      return;
    }

    completeSignupWithLink(url)
      .then(() => setStage("set-password"))
      .catch((err) => {
        setError(err instanceof Error ? err.message : "This link is invalid or has expired.");
        setStage("error");
      });
    // Only ever needs to run once, against the link the page was opened with.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleManualEmailSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await completeSignupWithLink(window.location.href, manualEmail);
      setStage("set-password");
    } catch (err) {
      setError(err instanceof Error ? err.message : "This link is invalid or has expired.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePasswordSubmit(e: FormEvent) {
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
      await setInitialPassword(password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set your password.");
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

        {stage === "completing" && (
          <>
            <h1 className="font-display text-2xl font-semibold text-paper">Confirming…</h1>
            <p className="mt-1 text-sm text-slate">One second, verifying your link.</p>
          </>
        )}

        {stage === "error" && (
          <>
            <h1 className="font-display text-2xl font-semibold text-paper">Link no longer valid</h1>
            <p className="mt-2 rounded-md border border-danger/30 bg-dangerDim px-3 py-2 text-sm text-danger">
              {error}
            </p>
            <p className="mt-4 text-sm text-slate">
              Head back to signup and request a fresh link.
            </p>
          </>
        )}

        {stage === "need-email" && (
          <>
            <h1 className="font-display text-2xl font-semibold text-paper">Confirm your email</h1>
            <p className="mt-1 text-sm text-slate">
              Looks like this link was opened on a different device or browser than you requested
              it from — enter the email you signed up with to finish.
            </p>
            <form onSubmit={handleManualEmailSubmit} className="mt-6 space-y-4">
              <input
                type="email"
                required
                autoComplete="email"
                className="field-input"
                value={manualEmail}
                onChange={(e) => setManualEmail(e.target.value)}
                placeholder="you@studio.com"
              />
              {error && (
                <p className="rounded-md border border-danger/30 bg-dangerDim px-3 py-2 text-sm text-danger">
                  {error}
                </p>
              )}
              <button type="submit" disabled={submitting} className="btn-primary w-full">
                {submitting ? "Confirming…" : "Continue"}
              </button>
            </form>
          </>
        )}

        {stage === "set-password" && (
          <>
            <h1 className="font-display text-2xl font-semibold text-paper">Set your password</h1>
            <p className="mt-1 text-sm text-slate">
              Your email is confirmed. Pick a password to finish setting up your account.
            </p>
            <form onSubmit={handlePasswordSubmit} className="mt-6 space-y-4">
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
                {submitting ? "Saving…" : "Finish setting up"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
