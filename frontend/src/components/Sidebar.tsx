"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

// Ch.12c's workspace nav list, in order.
const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/channels", label: "Channels" },
  { href: "/analytics", label: "Analytics" },
  { href: "/billing", label: "Billing" },
  { href: "/providers", label: "API Providers" },
  { href: "/team", label: "Team" },
  { href: "/settings", label: "Settings" },
  { href: "/logs", label: "Logs" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  const router = useRouter();

  async function handleSignOut() {
    await signOut();
    router.replace("/login");
  }

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-line bg-panel">
      <div className="flex items-center gap-2.5 border-b border-line px-5 py-5">
        <span className="h-2.5 w-2.5 animate-pulseSignal rounded-full bg-signal" />
        <span className="font-display text-sm font-semibold tracking-wide text-paper">
          AI CARRYON
        </span>
      </div>

      <nav className="flex-1 space-y-0.5 px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded-md px-3 py-2 text-sm transition ${
                active
                  ? "bg-amberDim text-amber font-medium"
                  : "text-slate hover:bg-panel2 hover:text-paper"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-line px-4 py-4">
        <p className="truncate font-mono text-xs text-slate">{user?.email}</p>
        <button
          onClick={handleSignOut}
          className="mt-2 text-xs font-medium text-slate hover:text-danger"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
