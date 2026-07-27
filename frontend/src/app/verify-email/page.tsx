"use client";

/**
 * Ch.12g — shown right after signup (and after login, if a user somehow
 * never verified) instead of the dashboard. Polls the Firebase user
 * object every few seconds; onAuthStateChanged does NOT re-fire just
 * because emailVerified flipped, so this page calls reload() itself and
 * checks the flag directly rather than trusting AuthProvider's `user`.
 */
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { reload, deleteUser } from "firebase/auth";
import { useAuth } from "@/lib/auth-context";
import { getFirebaseAuth } from "@/lib/firebase";

const POLL_INTERVAL_MS = 3000;
const RESEND_COOLDOWN_S = 60;

export default function VerifyEmailPage() {
  const { user, loading, signOut, resendVerificationEmail } = useAuth();
  const router = useRouter();
  const [resendState, setResendState] = useState<"idle" | "sending" | "sent">("idle");
  const [resendError, setResendError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const cooldownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [startOverState, setStartOverState] = useState<"idle" | "working">("idle");
  const [startOverError, setStartOverError] = useState<string | null>(null);

  // Not signed in at all → nothing to verify, send them to log in.
  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  // Poll for the emailVerified flag flipping to true.
  useEffect(() => {
    if (!user) return;

    const interval = setInterval(async () => {
      const current = getFirebaseAuth().currentUser;
      if (!current) return;
      await reload(current);
      if (current.emailVerified) {
        clearInterval(interval);
        router.replace("/dashboard");
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [user, router]);

  function startCooldown() {
    setCooldown(RESEND_COOLDOWN_S);
    cooldownRef.current = setInterval(() => {
      setCooldown((s) => {
        if (s <= 1 && cooldownRef.current) {
          clearInterval(cooldownRef.current);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
  }

  useEffect(() => {
    return () => {
      if (cooldownRef.current) clearInterval(cooldownRef.current);
    };
  }, []);

  async function handleResend() {
    setResendError(null);
    setResendState("sending");
    try {
      await resendVerificationEmail();
      setResendState("sent");
      startCooldown();
    } catch (err) {
      setResendState("idle");
      setResendError(err instanceof Error ? err.message : "Could not resend the email.");
    }
  }

  // Ch.12h — for a genuine typo (not an attack), there's otherwise no way
  // out: the link went to someone else's inbox, so it will never be
  // clicked. Safe to delete outright here since an unverified account has
  // no real data attached to it yet — nothing is lost by starting over.
  async function handleStartOver() {
    setStartOverError(null);
    const current = getFirebaseAuth().currentUser;
    if (!current) {
      router.replace("/signup");
      return;
    }
    setStartOverState("working");
    try {
      await deleteUser(current);
      router.replace("/signup");
    } catch (err) {
      setStartOverState("idle");
      setStartOverError(
        err instanceof Error ? err.message : "Could not remove that account. Please try again."
      );
    }
  }

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
          We sent a verification link to{" "}
          <span className="font-medium text-paper">{user?.email}</span>. Click it to activate
          your account — this page will move on automatically once you do.
        </p>

        {resendError && (
          <p className="mt-4 rounded-md border border-danger/30 bg-dangerDim px-3 py-2 text-sm text-danger">
            {resendError}
          </p>
        )}

        <button
          type="button"
          onClick={handleResend}
          disabled={resendState === "sending" || cooldown > 0}
          className="btn-primary mt-6 w-full"
        >
          {cooldown > 0
            ? `Resend available in ${cooldown}s`
            : resendState === "sending"
            ? "Sending…"
            : "Resend verification email"}
        </button>

        <button
          type="button"
          onClick={() => signOut().then(() => router.replace("/login"))}
          className="mt-4 text-sm text-slate hover:underline"
        >
          Sign out
        </button>

        {startOverError && (
          <p className="mt-4 rounded-md border border-danger/30 bg-dangerDim px-3 py-2 text-sm text-danger">
            {startOverError}
          </p>
        )}

        <button
          type="button"
          onClick={handleStartOver}
          disabled={startOverState === "working"}
          className="mt-2 text-sm text-slate hover:underline"
        >
          {startOverState === "working" ? "Removing account…" : "Wrong email? Start over"}
        </button>
      </div>
    </div>
  );
}
