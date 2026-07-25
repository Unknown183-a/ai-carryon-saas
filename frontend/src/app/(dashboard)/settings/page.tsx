"use client";

import { useAuth } from "@/lib/auth-context";

export default function SettingsPage() {
  const { user, workspace } = useAuth();

  return (
    <div className="max-w-2xl">
      <h1 className="font-display text-2xl font-semibold text-paper">Settings</h1>
      <p className="mt-1 text-sm text-slate">Account and workspace identifiers.</p>

      <div className="panel mt-6 divide-y divide-line">
        <Row label="Email" value={user?.email ?? "—"} />
        <Row label="User ID" value={user?.uid ?? "—"} mono />
        <Row label="Workspace ID" value={(workspace?.workspace_id as string) ?? "—"} mono />
      </div>

      <div className="panel mt-6 border-dashed px-6 py-8 text-center">
        <p className="text-sm text-paper">Deeper settings aren't wired up yet.</p>
        <p className="mt-1.5 text-sm text-slate">
          Things like display name, notification preferences, and default channel
          settings need dedicated backend fields that don't exist yet.
        </p>
      </div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between px-5 py-3.5">
      <span className="text-sm text-slate">{label}</span>
      <span className={`text-sm text-paper ${mono ? "font-mono text-xs" : ""}`}>{value}</span>
    </div>
  );
}
