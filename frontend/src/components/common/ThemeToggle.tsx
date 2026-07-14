"use client";

import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";

interface ThemeToggleProps {
  collapsed?: boolean;
}

export function ThemeToggle({ collapsed }: ThemeToggleProps) {
  const { resolvedTheme, setTheme } = useTheme();

  const toggle = () => setTheme(resolvedTheme === "dark" ? "light" : "dark");

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size={collapsed ? "icon" : "sm"}
            onClick={toggle}
            aria-label="Toggle theme"
            className="text-muted-foreground hover:text-foreground"
          >
            {resolvedTheme === "dark" ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
            {!collapsed && (
              <span className="text-sm">
                {resolvedTheme === "dark" ? "Light" : "Dark"}
              </span>
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">
          {resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
