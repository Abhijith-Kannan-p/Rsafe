import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "../lib/cn";

type Variant = "primary" | "ghost" | "danger" | "success";
type Size = "sm" | "md" | "lg";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
  iconRight?: ReactNode;
  loading?: boolean;
};

const VARIANT: Record<Variant, string> = {
  primary:
    "bg-saffron text-ink shadow-[0_6px_24px_rgba(255,180,59,0.35)] hover:brightness-105 hover:shadow-[0_8px_30px_rgba(255,180,59,0.5)]",
  ghost: "glass !rounded-full text-cream hover:bg-white/15",
  danger: "bg-coral text-ink hover:brightness-105",
  success: "bg-aqua text-ink hover:brightness-105",
};

const SIZE: Record<Size, string> = {
  sm: "h-9 px-4 text-sm gap-1.5",
  md: "h-11 px-5 text-[15px] gap-2",
  lg: "h-14 px-7 text-base gap-2.5",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", icon, iconRight, loading, disabled, className, children, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex select-none items-center justify-center rounded-full font-semibold transition",
        "active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:outline-2 focus-visible:outline-offset-[3px] focus-visible:outline-saffron",
        VARIANT[variant],
        SIZE[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
      {children}
      {iconRight}
    </button>
  );
});
