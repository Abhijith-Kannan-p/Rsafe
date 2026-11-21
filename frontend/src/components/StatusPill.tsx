import { cn } from "../lib/cn";

export type Status =
  | "ready"
  | "fixing"
  | "blocked"
  | "open"
  | "held"
  | "approved"
  | "edited"
  | "verified";

const STYLE: Record<Status, { dot: string; cls: string; label: string }> = {
  ready: { dot: "bg-aqua", cls: "text-aqua bg-aqua/10", label: "Ready" },
  verified: { dot: "bg-aqua", cls: "text-aqua bg-aqua/10", label: "Verified" },
  approved: { dot: "bg-aqua", cls: "text-aqua bg-aqua/10", label: "Approved" },
  fixing: { dot: "bg-saffron", cls: "text-saffron bg-saffron/10", label: "Fixing" },
  edited: { dot: "bg-violet", cls: "text-violet bg-violet/10", label: "Edited" },
  open: { dot: "bg-cream", cls: "text-cream bg-white/10", label: "Open" },
  blocked: { dot: "bg-coral", cls: "text-coral bg-coral/10", label: "Blocked" },
  held: { dot: "bg-coral", cls: "text-coral bg-coral/10", label: "Held" },
};

export function StatusPill({ status, label, className }: { status: Status; label?: string; className?: string }) {
  const s = STYLE[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", s.cls, className)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", s.dot)} aria-hidden />
      {label ?? s.label}
    </span>
  );
}
