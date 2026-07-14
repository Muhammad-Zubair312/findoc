"use client";

import { useState } from "react";
import { useTheme } from "next-themes";
import {
  User,
  Palette,
  Keyboard,
  LogOut,
  Check,
  Monitor,
  Moon,
  Sun,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/lib/hooks/useAuth";
import { cn } from "@/lib/utils";
import { format, parseISO } from "date-fns";

// ─── Nav items ────────────────────────────────────────────────────────────────

type Section = "profile" | "appearance" | "shortcuts" | "account";

const NAV_ITEMS: { id: Section; label: string; icon: React.ReactNode }[] = [
  { id: "profile", label: "Profile", icon: <User className="h-4 w-4" /> },
  {
    id: "appearance",
    label: "Appearance",
    icon: <Palette className="h-4 w-4" />,
  },
  {
    id: "shortcuts",
    label: "Shortcuts",
    icon: <Keyboard className="h-4 w-4" />,
  },
  { id: "account", label: "Account", icon: <LogOut className="h-4 w-4" /> },
];

// ─── Keyboard shortcuts reference ─────────────────────────────────────────────

const SHORTCUTS = [
  { action: "Open command palette / search", keys: ["⌘", "K"] },
  { action: "Toggle sidebar", keys: ["⌘", "B"] },
  { action: "Focus chat input", keys: ["⌘", "/"] },
  { action: "Send message", keys: ["↵"] },
  { action: "New line in chat", keys: ["⇧", "↵"] },
  { action: "Scroll to bottom", keys: ["↓"] },
];

// ─── Theme option card ────────────────────────────────────────────────────────

interface ThemeCardProps {
  value: string;
  label: string;
  icon: React.ReactNode;
  active: boolean;
  onClick: () => void;
}

function ThemeCard({ value, label, icon, active, onClick }: ThemeCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "relative flex flex-col gap-3 rounded-xl border-2 p-4 text-left transition-all duration-150 hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active ? "border-[#7C3AED] bg-[#7C3AED]/5" : "border-border"
      )}
      aria-pressed={active}
    >
      {/* Mini UI preview */}
      <ThemePreview theme={value} />

      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">{icon}</span>
        <span className="text-[13px] font-medium text-foreground capitalize">
          {label}
        </span>
      </div>

      {active && (
        <span className="absolute top-2.5 right-2.5 h-5 w-5 rounded-full bg-[#7C3AED] flex items-center justify-center">
          <Check className="h-3 w-3 text-white" />
        </span>
      )}
    </button>
  );
}

function ThemePreview({ theme }: { theme: string }) {
  const isDark = theme === "dark" || theme === "system";
  const isLight = theme === "light";

  if (theme === "system") {
    return (
      <div className="h-16 rounded-lg overflow-hidden flex border border-border/50">
        <div className="flex-1 bg-[#0f1117] p-2 space-y-1">
          <div className="h-1.5 w-8 bg-[#1F4E79]/60 rounded" />
          <div className="h-1 w-12 bg-gray-700 rounded" />
          <div className="h-1 w-10 bg-gray-700 rounded" />
        </div>
        <div className="flex-1 bg-white p-2 space-y-1">
          <div className="h-1.5 w-8 bg-[#1F4E79]/60 rounded" />
          <div className="h-1 w-12 bg-gray-200 rounded" />
          <div className="h-1 w-10 bg-gray-200 rounded" />
        </div>
      </div>
    );
  }

  const bg = isLight ? "bg-white" : "bg-[#0f1117]";
  const barColor = isLight ? "bg-gray-200" : "bg-gray-700";

  return (
    <div className={cn("h-16 rounded-lg border border-border/50 p-2 space-y-1.5", bg)}>
      <div className="h-1.5 w-8 bg-[#1F4E79]/60 rounded" />
      <div className={cn("h-1 w-16 rounded", barColor)} />
      <div className={cn("h-1 w-12 rounded", barColor)} />
      <div className={cn("h-1 w-14 rounded", barColor)} />
    </div>
  );
}

// ─── Avatar initials ──────────────────────────────────────────────────────────

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

// ─── SettingsView ─────────────────────────────────────────────────────────────

export function SettingsView() {
  const [activeSection, setActiveSection] = useState<Section>("profile");
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Sidebar nav ───────────────────────────────────────────────────── */}
      <nav
        className="w-48 shrink-0 border-r border-border p-4 space-y-0.5 overflow-y-auto scrollbar-thin"
        aria-label="Settings sections"
      >
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setActiveSection(item.id)}
            className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-colors text-left",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              activeSection === item.id
                ? "bg-[#1F4E79]/10 text-[#1F4E79]"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
            )}
            aria-current={activeSection === item.id ? "page" : undefined}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </nav>

      {/* ── Main content ──────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="max-w-2xl px-8 py-8 space-y-8">
          {activeSection === "profile" && (
            <ProfileSection user={user} />
          )}
          {activeSection === "appearance" && (
            <AppearanceSection theme={theme} setTheme={setTheme} />
          )}
          {activeSection === "shortcuts" && <ShortcutsSection />}
          {activeSection === "account" && (
            <AccountSection onLogout={logout} />
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Section: Profile ─────────────────────────────────────────────────────────

function ProfileSection({
  user,
}: {
  user: { full_name: string; email: string; created_at: string } | null;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-foreground">Profile</h2>
        <p className="text-[13px] text-muted-foreground mt-0.5">
          Your account information.
        </p>
      </div>

      <Separator />

      {/* Avatar + name */}
      <div className="flex items-center gap-4">
        <div className="h-16 w-16 rounded-full bg-gradient-to-br from-[#1F4E79] to-[#7C3AED] flex items-center justify-center shrink-0">
          <span className="text-xl font-bold text-white">
            {user ? getInitials(user.full_name) : "?"}
          </span>
        </div>
        <div>
          <p className="text-base font-semibold text-foreground">
            {user?.full_name ?? "—"}
          </p>
          <p className="text-[13px] text-muted-foreground">{user?.email ?? "—"}</p>
        </div>
      </div>

      {/* Info rows */}
      <div className="space-y-4">
        <InfoRow label="Full name" value={user?.full_name ?? "—"} />
        <InfoRow label="Email address" value={user?.email ?? "—"} />
        <InfoRow
          label="Member since"
          value={
            user?.created_at
              ? format(parseISO(user.created_at), "MMMM d, yyyy")
              : "—"
          }
        />
      </div>

      <p className="text-[12px] text-muted-foreground">
        Profile editing is not yet available in this version.
      </p>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[12px] font-medium text-muted-foreground">
        {label}
      </label>
      <div className="flex h-9 items-center px-3 rounded-lg border border-border bg-muted/30 text-[13px] text-foreground">
        {value}
      </div>
    </div>
  );
}

// ─── Section: Appearance ──────────────────────────────────────────────────────

function AppearanceSection({
  theme,
  setTheme,
}: {
  theme: string | undefined;
  setTheme: (theme: string) => void;
}) {
  const options = [
    { value: "dark", label: "Dark", icon: <Moon className="h-4 w-4" /> },
    { value: "light", label: "Light", icon: <Sun className="h-4 w-4" /> },
    { value: "system", label: "System", icon: <Monitor className="h-4 w-4" /> },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-foreground">Appearance</h2>
        <p className="text-[13px] text-muted-foreground mt-0.5">
          Choose your preferred color theme.
        </p>
      </div>

      <Separator />

      <div>
        <p className="text-[13px] font-medium text-foreground mb-3">Theme</p>
        <div className="grid grid-cols-3 gap-3">
          {options.map((opt) => (
            <ThemeCard
              key={opt.value}
              value={opt.value}
              label={opt.label}
              icon={opt.icon}
              active={theme === opt.value}
              onClick={() => setTheme(opt.value)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Section: Shortcuts ───────────────────────────────────────────────────────

function ShortcutsSection() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-foreground">
          Keyboard Shortcuts
        </h2>
        <p className="text-[13px] text-muted-foreground mt-0.5">
          Global shortcuts available throughout the app.
        </p>
      </div>

      <Separator />

      <div className="rounded-xl border border-border overflow-hidden">
        <table className="w-full text-[13px]" role="table">
          <thead>
            <tr className="bg-muted/40 border-b border-border">
              <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                Action
              </th>
              <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">
                Shortcut
              </th>
            </tr>
          </thead>
          <tbody>
            {SHORTCUTS.map((shortcut, i) => (
              <tr
                key={shortcut.action}
                className={cn(
                  "border-b border-border last:border-0",
                  i % 2 === 0 ? "bg-card" : "bg-muted/10"
                )}
              >
                <td className="px-4 py-3 text-foreground">{shortcut.action}</td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center gap-1 justify-end">
                    {shortcut.keys.map((key) => (
                      <kbd
                        key={key}
                        className="inline-flex items-center justify-center h-6 min-w-[1.5rem] px-1.5 rounded-md border border-border bg-muted text-[11px] font-mono font-medium text-foreground"
                      >
                        {key}
                      </kbd>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-[12px] text-muted-foreground">
        On Windows/Linux, use Ctrl in place of ⌘.
      </p>
    </div>
  );
}

// ─── Section: Account ─────────────────────────────────────────────────────────

function AccountSection({ onLogout }: { onLogout: () => void }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-foreground">Account</h2>
        <p className="text-[13px] text-muted-foreground mt-0.5">
          Manage your session and account.
        </p>
      </div>

      <Separator />

      {/* Sign out */}
      <div className="rounded-xl border border-border p-5 space-y-3">
        <div>
          <p className="text-[13px] font-semibold text-foreground">Sign out</p>
          <p className="text-[12px] text-muted-foreground mt-0.5">
            Sign out of your account on this device.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onLogout}
          className="gap-2"
        >
          <LogOut className="h-3.5 w-3.5" />
          Sign out
        </Button>
      </div>

      {/* Danger zone */}
      <div className="rounded-xl border border-danger/30 p-5 space-y-3">
        <div>
          <p className="text-[13px] font-semibold text-danger">Danger zone</p>
          <p className="text-[12px] text-muted-foreground mt-0.5">
            Permanently delete your account and all associated data. This
            action cannot be undone.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled
          className="gap-2 border-danger/30 text-danger/60 cursor-not-allowed"
        >
          Delete account
        </Button>
        <p className="text-[11px] text-muted-foreground">
          Account deletion is not yet available. Contact support to request it.
        </p>
      </div>
    </div>
  );
}
