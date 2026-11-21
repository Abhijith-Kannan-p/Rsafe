import { AlertOctagon, AlertTriangle, Info } from "lucide-react";
import { cn } from "../lib/cn";

export type Severity = "high" | "medium" | "low";

const STYLE: Record<Severity, { cls: string; Icon: typeof Info; label: string }> = {
  high: { cls: "bg-coral/15 text-coral ring-coral/40", Icon: AlertOctagon, label: "High" },
  medium: { cls: "bg-saffron/15 text-saffron ring-saffron/40", Icon: AlertTriangle, label: "Medium" },
  low: { cls: "bg-violet/15 text-violet ring-violet/40", Icon: Info, label: "Low" },
};

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const { cls, Icon, label } = STYLE[severity];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset",
        cls,
        className,
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {label}
      <span className="sr-only"> severity</span>
    </span>
  );
}
