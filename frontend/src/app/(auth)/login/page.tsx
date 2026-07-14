"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { AuthPanel } from "@/components/common/AuthPanel";
import { useAuth } from "@/lib/hooks/useAuth";
import { cn } from "@/lib/utils";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type LoginFormData = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const { login, isLoginPending } = useAuth();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = (data: LoginFormData) => {
    login({ email: data.email, password: data.password });
  };

  return (
    // ── Outer shell: fills viewport, scrollable on tiny phones ──────────────
    <div className="flex min-h-screen overflow-y-auto bg-background">

      {/* ── Form panel ───────────────────────────────────────────────────── */}
      {/* On mobile: full width, comfortable padding                         */}
      {/* On lg+: capped at 540 px, AuthPanel fills the rest                 */}
      <div className="flex flex-1 flex-col items-center justify-center
                      px-5 py-8
                      sm:px-8 sm:py-10
                      lg:px-16 lg:py-12 lg:max-w-[540px]">

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="w-full max-w-[380px] space-y-6 sm:space-y-8"
        >
          {/* ── Logo + heading ─────────────────────────────────────────── */}
          <div className="flex flex-col items-center gap-3 sm:gap-4 text-center">
            {/* Logo badge — slightly smaller on mobile */}
            <div className="flex h-12 w-12 sm:h-14 sm:w-14 items-center justify-center
                            rounded-2xl bg-[#1F4E79]
                            shadow-lg shadow-[#1F4E79]/30 ring-1 ring-[#7C3AED]/20">
              <Image src="/logo.svg" alt="FinDoc" width={28} height={28}
                     className="sm:w-8 sm:h-8" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
                FinDoc Intelligence
              </h1>
              <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
                Sign in to your workspace
              </p>
            </div>
          </div>

          {/* ── Form ───────────────────────────────────────────────────── */}
          <form onSubmit={handleSubmit(onSubmit)}
                className="space-y-3 sm:space-y-4" noValidate>

            {/* Email */}
            <div className="space-y-1.5">
              <Label htmlFor="login-email" className="text-sm font-medium">
                Email address
              </Label>
              <Input
                id="login-email"
                type="email"
                autoComplete="email"
                placeholder="analyst@firm.com"
                aria-invalid={!!errors.email}
                className={cn(
                  // h-11 = 44 px — good touch target on mobile
                  "h-11 bg-muted/40 border-border/60 focus:bg-background transition-colors",
                  errors.email && "border-destructive focus-visible:ring-destructive/50"
                )}
                {...register("email")}
              />
              {errors.email && (
                <p className="text-xs text-destructive" role="alert">
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <Label htmlFor="login-password" className="text-sm font-medium">
                Password
              </Label>
              <div className="relative">
                <Input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  aria-invalid={!!errors.password}
                  className={cn(
                    "[&::-ms-reveal]:hidden [&::-webkit-credentials-auto-fill-button]:hidden",
                    "h-11 pr-10 bg-muted/40 border-border/60 focus:bg-background transition-colors",
                    errors.password && "border-destructive focus-visible:ring-destructive/50"
                  )}
                  {...register("password")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2
                             text-muted-foreground hover:text-foreground transition-colors
                             p-1 -mr-1" // extra tap area on mobile
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  tabIndex={-1}
                >
                  {showPassword
                    ? <EyeOff className="h-4 w-4" />
                    : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="text-xs text-destructive" role="alert">
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Submit */}
            <Button
              type="submit"
              className={cn(
                "w-full h-11 text-sm font-semibold mt-2 gap-2",
                "bg-[#7C3AED] hover:bg-[#6d33d4] text-white",
                "shadow-md shadow-[#7C3AED]/20 hover:shadow-lg hover:shadow-[#7C3AED]/30",
                "transition-all duration-200",
                // active feedback for touch devices
                "active:scale-[0.98]"
              )}
              disabled={isLoginPending}
            >
              {isLoginPending ? (
                <><LoadingSpinner size="sm" />Signing in...</>
              ) : (
                <>Sign in<ArrowRight className="h-4 w-4" /></>
              )}
            </Button>
          </form>

          {/* ── Divider ────────────────────────────────────────────────── */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border/50" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-background px-3 text-[11px] text-muted-foreground uppercase tracking-wider">
                New to FinDoc?
              </span>
            </div>
          </div>

          {/* ── Register link ──────────────────────────────────────────── */}
          <Link
            href="/register"
            className={cn(
              "flex items-center justify-center gap-2 w-full h-11 rounded-lg",
              "border border-border/60 bg-muted/30 hover:bg-muted/60",
              "text-sm font-medium text-foreground transition-all duration-150",
              "active:scale-[0.98]"
            )}
          >
            Create an account
          </Link>
        </motion.div>
      </div>

      {/* ── Brand panel — hidden on mobile, visible lg+ ──────────────────── */}
      <AuthPanel />
    </div>
  );
}