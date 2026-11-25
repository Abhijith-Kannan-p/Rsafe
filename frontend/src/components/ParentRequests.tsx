import { CheckCircle2, MessageSquareWarning } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { post, type Handled, type IssueBrief, type ParentRequest, type ParentRequests as Data } from "../lib/api";
import { cn } from "../lib/cn";
import { useApi } from "../lib/useApi";
import { Button } from "./Button";
import { GlassCard } from "./GlassCard";
import { useToast } from "./Toast";
import { formatTime } from "./ui";

const ACTIVE = new Set(["open", "held"]);

function Chip({ i, onOpen }: { i: IssueBrief; onOpen: (id: number) => void }) {
  const active = ACTIVE.has(i.status);
  return (
    <button
      type="button"
      onClick={() => onOpen(i.id)}
      title={`${i.title} (${i.status})`}
      aria-label={`Open ${i.rule_id}: ${i.title}, ${i.status}`}
      className={cn(
        "rounded-full px-2.5 py-0.5 font-mono text-xs font-semibold ring-1 ring-inset transition hover:brightness-125 focus-visible:outline-2 focus-visible:outline-saffron",
        active ? "bg-saffron/15 text-saffron ring-saffron/40" : "bg-aqua/10 text-aqua ring-aqua/30",
      )}
    >
      {i.rule_id} · {active ? i.status : "decided"}
    </button>
  );
}

function Request({ r, canHandle, showSchool, onOpen, onHandled }: {
  r: ParentRequest; canHandle: boolean; showSchool: boolean;
  onOpen: (id: number) => void; onHandled: () => void;
}) {
  const toast = useToast();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const markHandled = async () => {
    setBusy(true);
    try {
      const res = await post<{ audit_id: number; handled: Handled }>(`/parent-requests/${r.id}/handled`, { note });
      toast({ kind: "success", title: "Marked as handled", body: `Written to the audit log as entry #${res.audit_id}. The record was not changed.` });
      onHandled();
    } catch (e) {
      toast({ kind: "error", title: "Could not mark as handled", body: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className={cn("rounded-2xl p-3", r.handled ? "bg-white/[0.03]" : "bg-white/[0.06]")}>
      <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
        <span className="font-medium text-cream">{r.name || <span className="italic text-coral">(no name)</span>}</span>
        <span className="font-mono text-xs text-mist">{r.student_ref}</span>
        <span className="text-xs text-mist">· class {r.class}{showSchool && ` · ${r.school_code}`}</span>
        <span className="ml-auto text-xs text-mist">{formatTime(r.ts)}</span>
      </p>
      <blockquote className="mt-2 border-l-2 border-violet/60 pl-3 text-sm text-cream">"{r.comment}"</blockquote>

      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-mist">
        {r.issues.length ? (
          <>
            <span>Issues on this record (open one to fix it):</span>
            {r.issues.map((i) => <Chip key={i.id} i={i} onOpen={onOpen} />)}
          </>
        ) : (
          <span>Rsafe found no issue on this record. Correct it in the school's own system and import again.</span>
        )}
      </div>

      {r.handled ? (
        <p className="mt-2 text-xs text-aqua">
          <CheckCircle2 className="mr-1 inline h-4 w-4 align-[-3px]" aria-hidden />
          Handled by {r.handled.actor.replace(/^Demo\s+/, "")} on {formatTime(r.handled.ts)}
          {r.handled.note && <span className="text-mist">. Note: {r.handled.note}</span>}
        </p>
      ) : canHandle ? (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs text-mist">
            <span className="sr-only">Note for request from {r.name || r.student_ref}</span>
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={300}
              placeholder="Optional note, e.g. name corrected from birth certificate"
              className="h-9 rounded-xl border border-white/15 bg-bg-mid/70 px-3 text-sm text-cream placeholder:text-mist/70 focus-visible:outline-2 focus-visible:outline-saffron"
            />
          </label>
          <Button size="sm" variant="success" loading={busy} onClick={markHandled} icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}>
            Mark as handled
          </Button>
        </div>
      ) : (
        <p className="mt-2 text-xs text-mist">Waiting for the school to handle it.</p>
      )}
    </li>
  );
}

/** Parents' "Something is wrong" replies, for the principal, the child's teachers and the MIS coordinator. */
export function ParentRequests({ onOpen, showSchool = false, refreshKey, className = "mt-4" }: {
  onOpen: (issueId: number) => void;
  showSchool?: boolean;
  className?: string;
  /** Changes whenever the page reloads its issues, so the issue chips here stay current. */
  refreshKey?: unknown;
}) {
  const data = useApi<Data>("/parent-requests");
  const { reload } = data;
  const first = useRef(true);
  useEffect(() => {
    if (first.current) first.current = false;
    else reload();
  }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const d = data.data;
  if (!d || d.requests.length === 0) return null;
  const pending = d.requests.filter((r) => !r.handled);
  const handled = d.requests.filter((r) => r.handled);
  const item = (r: ParentRequest) => (
    <Request key={r.id} r={r} canHandle={d.can_handle} showSchool={showSchool} onOpen={onOpen} onHandled={data.reload} />
  );

  return (
    <GlassCard className={cn("border-violet/30", className)} padding="sm" aria-labelledby="parent-req-title" data-tour="parent-requests">
      <div className="flex flex-wrap items-center gap-2 px-2 pb-2">
        <MessageSquareWarning className="h-5 w-5 text-violet" aria-hidden />
        <h2 id="parent-req-title" className="font-display text-lg font-semibold text-cream">Parent requests</h2>
        <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold", pending.length ? "bg-violet/20 text-violet" : "bg-aqua/10 text-aqua")}>
          {pending.length ? `${pending.length} waiting` : "All handled"}
        </span>
        <span className="text-sm text-mist">A parent said something in the record is wrong. Nothing changes until a person fixes it.</span>
      </div>
      {pending.length > 0 && <ul className="grid gap-2 lg:grid-cols-2">{pending.map(item)}</ul>}
      {handled.length > 0 && (
        <details className="mt-2 px-2">
          <summary className="cursor-pointer text-sm text-mist hover:text-cream">Handled ({handled.length})</summary>
          <ul className="mt-2 grid gap-2 lg:grid-cols-2">{handled.map(item)}</ul>
        </details>
      )}
    </GlassCard>
  );
}
