"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function RootPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? "/dashboard" : "/login");
  }, [user, loading, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink">
      <div className="flex items-center gap-3 text-sm text-slate">
        <span className="h-2 w-2 animate-pulseSignal rounded-full bg-signal" />
        Booting mission control…
      </div>
    </div>
  );
}
