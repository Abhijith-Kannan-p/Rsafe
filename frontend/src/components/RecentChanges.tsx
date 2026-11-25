import { History } from "lucide-react";
import { useEffect, useRef } from "react";
import { qs } from "../lib/api";
import { cn } from "../lib/cn";
import { useApi } from "../lib/useApi";
import { GlassCard } from "./GlassCard";
import { formatTime } from "./ui";

type Decision = {
  audit_id: number;
  ts: string;
  actor: string;
  role: string;
  action: "approve" | "confirm" | "edit" | "hold" | "reject_suggestion";
  issue_id: number | null;
  rule_id: string | null;
  school_code: string;
  entity: string;
  record: string;
  name: string;
  field: string | null;
  old: unknown;
  new: unknown;
  rejected_value: unknown;
  note: string;
};

const ACTION: Record<Decision["action"], string> = {
  approve: "approved the fix",
  confirm: "confirmed the record is right",
  edit: "edited",
  hold: "held for review",
  reject_suggestion: "rejected the suggestion",
};

const ROLE_TONE: Record<string, string> = {
  teacher: "bg-violet/20 text-violet",
  principal: "bg-saffron/15 text-saffron",
};

const show = (v: unknown) => (v === null || v === undefined || v === "" ? "(empty)" : `"${String(v)}"`);
const who = (d: Decision) => d.actor.replace(/^Demo\s+/, "");

/** The latest decisions people made on issues, so a principal sees teachers' changes on the Dashboard. */
export function RecentChanges({ schoolCode, refreshKey, showSchool, onOpen, onSeeAll }: {
  schoolCode?: string;
  refreshKey?: unknown;
  showSchool?: boolean;
  onOpen: (issueId: number) => void;
  onSeeAll: () => void;
}) {
  const data = useApi<{ decisions: Decision[]; by_teacher: number }>(`/decisions${qs({ school_code: schoolCode, limit: "8" })}`);
  const { reload } = data;
  const first = useRef(true);
  useEffect(() => {
    if (first.current) first.current = false;
    else reload();
  }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const d = data.data;
  if (!d || d.decisions.length === 0) return null;

  return (
    <GlassCard className="mt-4" padding="sm" aria-labelledby="recent-title" data-tour="recent-changes">
      <div className="flex flex-wrap items-center gap-2 px-2 pb-2">
        <History className="h-5 w-5 text-aqua" aria-hidden />
        <h2 id="recent-title" className="font-display text-lg font-semibold text-cream">Recent changes</h2>
        {d.by_teacher > 0 && (
          <span className="rounded-full bg-violet/20 px-2 py-0.5 text-xs font-semibold text-violet">
            {d.by_teacher} by teachers
          </span>
        )}
        <span className="text-sm text-mist">Every decision on an issue, newest first, from the audit log.</span>
        <button type="button" onClick={onSeeAll}
          className="ml-auto rounded-full px-3 py-1 text-sm text-saffron hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-saffron">
          See all decided issues →
        </button>
      </div>
      <ul className="grid gap-1.5">
        {d.decisions.map((x) => (
          <li key={x.audit_id}>
            <button
              type="button"
              disabled={!x.issue_id}
              onClick={() => x.issue_id && onOpen(x.issue_id)}
              className="w-full rounded-2xl bg-white/[0.04] px-3 py-2 text-left text-sm transition hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-saffron"
            >
              <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold", ROLE_TONE[x.role] ?? "bg-white/10 text-cream")} title={x.actor}>
                  {who(x)}
                </span>
                <span className="text-cream">{ACTION[x.action] ?? x.action}</span>
                <span className="font-medium text-cream">{x.name || x.record}</span>
                <span className="font-mono text-xs text-mist">
                  {x.record}{x.rule_id && ` · ${x.rule_id}`}{showSchool && ` · ${x.school_code}`}
                </span>
                <span className="ml-auto text-xs text-mist">{formatTime(x.ts)}</span>
              </p>
              {(x.field || x.note) && (
                <p className="mt-1 text-xs text-mist">
                  {x.field && (x.action === "reject_suggestion" ? (
                    <>{x.field.replace(/_/g, " ")}: suggestion {show(x.rejected_value)} rejected</>
                  ) : (
                    <>
                      {x.field.replace(/_/g, " ")}: <span className="line-through decoration-coral/70">{show(x.old)}</span> →{" "}
                      <span className="text-aqua">{show(x.new)}</span>
                    </>
                  ))}
                  {x.field && x.note && " · "}
                  {x.note && <>Note: {x.note}</>}
                </p>
              )}
            </button>
          </li>
        ))}
      </ul>
    </GlassCard>
  );
}
