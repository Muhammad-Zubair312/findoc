"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  FileText,
  BarChart3,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  LogOut,
  ChevronDown,
} from "lucide-react";
import { useEffect } from "react";

import { useUIStore } from "@/lib/stores/uiStore";
import { useAuth } from "@/lib/hooks/useAuth";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/chat", label: "Chat", icon: MessageSquare, exact: false },
  { href: "/documents", label: "Documents", icon: FileText, exact: true },
  { href: "/dashboard", label: "Dashboard", icon: BarChart3, exact: true },
  { href: "/settings", label: "Settings", icon: Settings, exact: true },
] as const;

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function NavRail() {
  const pathname = usePathname();
  const { navCollapsed, toggleNav } = useUIStore();
  const { user, logout } = useAuth();

  // Cmd+B / Ctrl+B to toggle
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        toggleNav();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [toggleNav]);

  const isActive = (href: string, exact: boolean) =>
    exact ? pathname === href : pathname.startsWith(href);

  return (
    <TooltipProvider delayDuration={400}>
      <motion.aside
        animate={{ width: navCollapsed ? 64 : 240 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className="relative flex h-screen flex-col border-r border-border bg-card overflow-hidden shrink-0 z-30"
      >
        {/* Logo */}
        <div
          className={cn(
            "flex h-[60px] items-center border-b border-border px-4 shrink-0",
            navCollapsed ? "justify-center" : "gap-2"
          )}
        >
          <Link href="/chat" className="flex items-center gap-2 shrink-0">
            <Image src="/logo.svg" alt="FinDoc" width={28} height={28} priority />
            <AnimatePresence>
              {!navCollapsed && (
                <motion.span
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -6 }}
                  transition={{ duration: 0.15 }}
                  className="font-semibold text-[15px] text-foreground whitespace-nowrap"
                >
                  FinDoc
                </motion.span>
              )}
            </AnimatePresence>
          </Link>
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-3 space-y-0.5 px-2" aria-label="Main navigation">
          {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => {
            const active = isActive(href, exact);
            const item = (
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 py-2 px-2.5 rounded-lg transition-all duration-150 outline-none",
                  navCollapsed && "justify-center",
                  active
                    ? "bg-[#7C3AED]/10 text-[#7C3AED] shadow-[inset_3px_0_0_#7C3AED]"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
                )}
              >
                <Icon className="h-[18px] w-[18px] shrink-0" />
                <AnimatePresence>
                  {!navCollapsed && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.1 }}
                      className="text-sm font-medium whitespace-nowrap"
                    >
                      {label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </Link>
            );

            if (navCollapsed) {
              return (
                <Tooltip key={href}>
                  <TooltipTrigger asChild>{item}</TooltipTrigger>
                  <TooltipContent side="right" sideOffset={8}>
                    {label}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return <div key={href}>{item}</div>;
          })}
        </nav>

        {/* Bottom section */}
        <div className="shrink-0 border-t border-border p-2 space-y-0.5">
          {/* Theme toggle */}
          {navCollapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <div>
                  <ThemeToggle collapsed={navCollapsed} />
                </div>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={8}>
                Toggle theme
              </TooltipContent>
            </Tooltip>
          ) : (
            <ThemeToggle collapsed={navCollapsed} />
          )}

          {/* User dropdown */}
          {user && (
            <DropdownMenu>
              <Tooltip>
                <TooltipTrigger asChild>
                  <DropdownMenuTrigger asChild>
                    <button
                      className={cn(
                        "flex w-full items-center gap-2 rounded-lg p-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors duration-150 outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        navCollapsed && "justify-center"
                      )}
                      aria-label="User menu"
                    >
                      <Avatar className="h-6 w-6 shrink-0">
                        {user.avatar_url && (
                          <AvatarImage src={user.avatar_url} alt={user.full_name} />
                        )}
                        <AvatarFallback className="text-[10px]">
                          {getInitials(user.full_name)}
                        </AvatarFallback>
                      </Avatar>
                      <AnimatePresence>
                        {!navCollapsed && (
                          <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.1 }}
                            className="flex flex-1 items-center justify-between min-w-0"
                          >
                            <span className="truncate text-xs font-medium text-foreground">
                              {user.full_name}
                            </span>
                            <ChevronDown className="h-3 w-3 shrink-0 opacity-50" />
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </button>
                  </DropdownMenuTrigger>
                </TooltipTrigger>
                {navCollapsed && (
                  <TooltipContent side="right" sideOffset={8}>
                    {user.full_name}
                  </TooltipContent>
                )}
              </Tooltip>
              <DropdownMenuContent
                side="top"
                align={navCollapsed ? "center" : "start"}
                sideOffset={8}
                className="w-56"
              >
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col space-y-0.5">
                    <p className="text-sm font-medium leading-none">{user.full_name}</p>
                    <p className="text-xs leading-none text-muted-foreground">
                      {user.email}
                    </p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-danger focus:bg-danger/10 focus:text-danger"
                  onClick={() => logout()}
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}

          {/* Collapse toggle button */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={toggleNav}
                className="flex w-full items-center justify-center rounded-lg p-2 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors duration-150 outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label={navCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                {navCollapsed ? (
                  <PanelLeftOpen className="h-4 w-4" />
                ) : (
                  <div className="flex w-full items-center gap-2">
                    <PanelLeftClose className="h-4 w-4" />
                    <span className="text-sm">Collapse</span>
                    <kbd className="ml-auto text-[10px] font-mono opacity-50">⌘B</kbd>
                  </div>
                )}
              </button>
            </TooltipTrigger>
            {navCollapsed && (
              <TooltipContent side="right" sideOffset={8}>
                Expand sidebar <span className="opacity-60 ml-1 font-mono text-[10px]">⌘B</span>
              </TooltipContent>
            )}
          </Tooltip>
        </div>
      </motion.aside>
    </TooltipProvider>
  );
}
