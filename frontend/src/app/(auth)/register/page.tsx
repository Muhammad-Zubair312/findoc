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

// ─── Password strength ────────────────────────────────────────────────────────

interface StrengthResult {
  score: number;
  label: string;
  barColor: string;
  textColor: string;
}

function getStrength(password: string): StrengthResult {
  if (!password) return { score: 0, label: "", barColor: "", textColor: "" };
  let score = 0;
  if (password.length >= 8) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^a-zA-Z0-9]/.test(password) || password.length >= 14) score++;

  const map: StrengthResult[] = [
    { score: 0, label: "",       barColor: "",                 textColor: "" },
    { score: 1, label: "Weak",   barColor: "bg-red-500",       textColor: "text-red-500" },
    { score: 2, label: "Fair",   barColor: "bg-orange-400",    textColor: "text-orange-400" },
    { score: 3, label: "Good",   barColor: "bg-yellow-400",    textColor: "text-yellow-500" },
    { score: 4, label: "Strong", barColor: "bg-emerald-500",   textColor: "text-emerald-500" },
  ];
  return map[score] ?? map[0];
}

function PasswordStrengthBar({ password }: { password: string }) {
  const { score, label, barColor, textColor } = getStrength(password);
  if (!password) return null;
  return (
    <div className="space-y-1.5 pt-1">
      <div className="flex gap-1">
        {[1, 2, 3, 4].map((level) => (
          <div
            key={level}
            className={cn(
              "h-1 flex-1 rounded-full transition-all duration-300",
              score >= level ? barColor : "bg-muted"
            )}
          />
        ))}
      </div>
      {label && (
        <p className={cn("text-[11px] font-medium", textColor)}>{label}</p>
      )}
    </div>
  );
}

// ─── Schema ───────────────────────────────────────────────────────────────────

const registerSchema = z
  .object({
    full_name: z
      .string()
      .min(2, "Name must be at least 2 characters")
      .max(80, "Name is too long"),
    email: z.string().email("Enter a valid email address"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string(),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type RegisterFormData = z.infer<typeof registerSchema>;

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function RegisterPage() {
  const { register: registerUser, isRegisterPending } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm]   = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  });

  const passwordValue = watch("password", "");

  const onSubmit = (data: RegisterFormData) => {
    registerUser({
      email:     data.email,
      password:  data.password,
      full_name: data.full_name,
    });
  };

  const pwInputClass = cn(
    "[&::-ms-reveal]:hidden",
    "[&::-webkit-credentials-auto-fill-button]:hidden",
    "h-11 pr-10 bg-muted/40 border-border/60 focus:bg-background transition-colors"
  );

  return (
    // ── Outer shell ─────────────────────────────────────────────────────────
    // overflow-y-auto is critical for register: 4 fields + strength bar can
    // overflow on phones shorter than ~680 px (iPhone SE, Galaxy A-series etc.)
    <div className="flex min-h-screen overflow-y-auto bg-background">

      {/* ── Form panel ───────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col items-center justify-center
                      px-5 py-6
                      sm:px-8 sm:py-10
                      lg:px-16 lg:py-12 lg:max-w-[540px]">

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          // space-y-5 on mobile, relaxes to space-y-7 on sm+ screens
          className="w-full max-w-[380px] space-y-5 sm:space-y-7"
        >
          {/* ── Logo + heading ─────────────────────────────────────────── */}
          <div className="flex flex-col items-center gap-3 sm:gap-4 text-center">
            <div className="flex h-12 w-12 sm:h-14 sm:w-14 items-center justify-center
                            rounded-2xl bg-[#1F4E79]
                            shadow-lg shadow-[#1F4E79]/30 ring-1 ring-[#7C3AED]/20">
              <Image src="/logo.svg" alt="FinDoc" width={28} height={28}
                     className="sm:w-8 sm:h-8" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
                Create your account
              </h1>
              <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
                Start querying financial filings in seconds
              </p>
            </div>
          </div>

          {/* ── Form ───────────────────────────────────────────────────── */}
          {/* space-y-3 on mobile keeps fields compact; relaxes on sm+ */}
          <form onSubmit={handleSubmit(onSubmit)}
                className="space-y-3 sm:space-y-4" noValidate>

            {/* Full name */}
            <div className="space-y-1.5">
              <Label htmlFor="reg-name" className="text-sm font-medium">
                Full name
              </Label>
              <Input
                id="reg-name"
                type="text"
                autoComplete="name"
                placeholder="Jane Analyst"
                aria-invalid={!!errors.full_name}
                className={cn(
                  "h-11 bg-muted/40 border-border/60 focus:bg-background transition-colors",
                  errors.full_name && "border-destructive focus-visible:ring-destructive/50"
                )}
                {...register("full_name")}
              />
              {errors.full_name && (
                <p className="text-xs text-destructive" role="alert">
                  {errors.full_name.message}
                </p>
              )}
            </div>

            {/* Email */}
            <div className="space-y-1.5">
              <Label htmlFor="reg-email" className="text-sm font-medium">
                Email address
              </Label>
              <Input
                id="reg-email"
                type="email"
                autoComplete="email"
                placeholder="analyst@firm.com"
                aria-invalid={!!errors.email}
                className={cn(
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
              <Label htmlFor="reg-password" className="text-sm font-medium">
                Password
              </Label>
              <div className="relative">
                <Input
                  id="reg-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Min. 8 characters"
                  aria-invalid={!!errors.password}
                  className={cn(
                    pwInputClass,
                    errors.password && "border-destructive focus-visible:ring-destructive/50"
                  )}
                  {...register("password")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2
                             text-muted-foreground hover:text-foreground transition-colors
                             p-1 -mr-1"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  tabIndex={-1}
                >
                  {showPassword
                    ? <EyeOff className="h-4 w-4" />
                    : <Eye  className="h-4 w-4" />}
                </button>
              </div>
              {errors.password ? (
                <p className="text-xs text-destructive" role="alert">
                  {errors.password.message}
                </p>
              ) : (
                <PasswordStrengthBar password={passwordValue} />
              )}
            </div>

            {/* Confirm password */}
            <div className="space-y-1.5">
              <Label htmlFor="reg-confirm" className="text-sm font-medium">
                Confirm password
              </Label>
              <div className="relative">
                <Input
                  id="reg-confirm"
                  type={showConfirm ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Re-enter your password"
                  aria-invalid={!!errors.confirm_password}
                  className={cn(
                    pwInputClass,
                    errors.confirm_password && "border-destructive focus-visible:ring-destructive/50"
                  )}
                  {...register("confirm_password")}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2
                             text-muted-foreground hover:text-foreground transition-colors
                             p-1 -mr-1"
                  aria-label={showConfirm ? "Hide password" : "Show password"}
                  tabIndex={-1}
                >
                  {showConfirm
                    ? <EyeOff className="h-4 w-4" />
                    : <Eye  className="h-4 w-4" />}
                </button>
              </div>
              {errors.confirm_password && (
                <p className="text-xs text-destructive" role="alert">
                  {errors.confirm_password.message}
                </p>
              )}
            </div>

            {/* Submit */}
            <Button
              type="submit"
              className={cn(
                "w-full h-11 text-sm font-semibold mt-1 sm:mt-2 gap-2",
                "bg-[#7C3AED] hover:bg-[#6d33d4] text-white",
                "shadow-md shadow-[#7C3AED]/20 hover:shadow-lg hover:shadow-[#7C3AED]/30",
                "transition-all duration-200 active:scale-[0.98]"
              )}
              disabled={isRegisterPending}
            >
              {isRegisterPending ? (
                <><LoadingSpinner size="sm" />Creating account...</>
              ) : (
                <>Create account<ArrowRight className="h-4 w-4" /></>
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
                Already have an account?
              </span>
            </div>
          </div>

          {/* ── Login link ─────────────────────────────────────────────── */}
          <Link
            href="/login"
            className={cn(
              "flex items-center justify-center gap-2 w-full h-11 rounded-lg",
              "border border-border/60 bg-muted/30 hover:bg-muted/60",
              "text-sm font-medium text-foreground transition-all duration-150",
              "active:scale-[0.98]"
            )}
          >
            Sign in instead
          </Link>
        </motion.div>
      </div>

      {/* ── Brand panel — hidden on mobile, visible lg+ ──────────────────── */}
      <AuthPanel />
    </div>
  );
}