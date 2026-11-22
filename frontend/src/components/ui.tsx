import { AlertOctagon, Loader2 } from "lucide-react";
import type { ReactNode, SelectHTMLAttributes } from "react";
import { cn } from "../lib/cn";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-cream">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-mist">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  );
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & { label: string; hideLabel?: boolean };

export function Select({ label, hideLabel, className, children, id, ...rest }: SelectProps) {
  const sid = id ?? `sel-${label.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <label htmlFor={sid} className="flex flex-col gap-1 text-xs font-medium uppercase tracking-wider text-mist">
      <span className={cn(hideLabel && "sr-only")}>{label}</span>
      <select
        id={sid}
        className={cn(
          "h-10 rounded-xl border border-white/15 bg-bg-mid/70 px-3 text-sm normal-case tracking-normal text-cream",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-saffron",
          className,
        )}
        {...rest}
      >
        {children}
      </select>
    </label>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-10 text-mist">
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> {label}...
    </div>
  );
}

export function ErrorNote({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-2xl border border-coral/40 bg-coral/10 p-4 text-sm text-cream">
      <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0 text-coral" aria-hidden />
      <div className="flex-1">
        <p className="font-semibold">Something went wrong</p>
        <p className="text-mist">{error.message}</p>
      </div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="font-semibold text-saffron hover:underline">
          Try again
        </button>
      )}
    </div>
  );
}

export function Stat({ label, value, tone = "cream", hint }: { label: string; value: ReactNode; tone?: "cream" | "coral" | "saffron" | "violet" | "aqua"; hint?: string }) {
  const toneCls = { cream: "text-cream", coral: "text-coral", saffron: "text-saffron", violet: "text-violet", aqua: "text-aqua" }[tone];
  return (
    <div className="glass p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-mist">{label}</p>
      <p className={cn("mt-1 font-display text-3xl font-bold", toneCls)}>{value}</p>
      {hint && <p className="mt-1 text-xs text-mist">{hint}</p>}
    </div>
  );
}

/** Humanise snake_case keys for display. */
export const humanise = (k: string) => k.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export function formatValue(v: unknown): string {
  if (v === null || v === undefined || v === "") return "(empty)";
  if (Array.isArray(v)) return v.length ? v.map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x))).join(", ") : "(none)";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function formatTime(ts: string) {
  const d = new Date(ts);
  return isNaN(d.getTime()) ? ts : d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}
