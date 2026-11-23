import { Check, History, Info, PauseCircle, PencilLine, ShieldAlert, ThumbsDown } from "lucide-react";
import { useEffect, useState } from "react";
import { post, type ActionResult, type IssueDetail } from "../lib/api";
import { cn } from "../lib/cn";
import { htmlLang, MachineNote, useLang } from "../lib/i18n";
import { can, useIdentity } from "../lib/session";
import { useApi } from "../lib/useApi";
import { Button } from "./Button";
import { SidePanel } from "./Overlay";
import { SeverityBadge } from "./SeverityBadge";
import { StatusPill } from "./StatusPill";
import { useToast } from "./Toast";
import { ErrorNote, formatTime, formatValue, humanise, Loading } from "./ui";

/** Word-level diff: words only in `from` are struck in coral, words only in `to` glow aqua. */
function WordDiff({ from, to }: { from: string; to: string }) {
  const a = from.split(/\s+/).filter(Boolean);
  const b = to.split(/\s+/).filter(Boolean);
  const inA = new Set(a.map((w) => w.toLowerCase()));
  const inB = new Set(b.map((w) => w.toLowerCase()));
  return (
    <div className="grid gap-2 text-sm">
      <p>
        <span className="mr-2 text-xs uppercase tracking-wider text-mist">Now</span>
        {a.length === 0 && <span className="text-mist">(empty)</span>}
        {a.map((w, i) => (
          <span key={i} className={cn("mr-1", !inB.has(w.toLowerCase()) && "rounded bg-coral/20 px-1 text-coral line-through")}>
            {w}
          </span>
        ))}
      </p>
      <p>
        <span className="mr-2 text-xs uppercase tracking-wider text-mist">Fix</span>
        {b.map((w, i) => (
          <span key={i} className={cn("mr-1", !inA.has(w.toLowerCase()) && "rounded bg-aqua/20 px-1 font-semibold text-aqua")}>
            {w}
          </span>
        ))}
      </p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-mist">{title}</h3>
      {children}
    </section>
  );
}

const FIELD_HINT: Record<string, string> = {
  dob: "DD/MM/YYYY",
  gender: "M, F or T",
  class_grade: "1 to 12",
  aadhaar_status: "verified, missing or update_pending",
  enrolment_status: "active, dropout or transferred",
  transfer_status: "transferred_in or transferred_out",
  status: "functional or non_functional",
};

type Props = { issueId: number | null; onClose: () => void; onChanged: (r: ActionResult) => void };
type Action = "approve" | "edit" | "hold" | "reject-suggestion";

const HISTORY_LABEL: Record<string, string> = {
  approve: "Approved the suggested fix", confirm: "Confirmed the record is right", edit: "Edited the value",
  hold: "Held for review", reject_suggestion: "Rejected the suggestion",
};

/** "Why was this flagged?": the rule exactly as loaded, the data its check reads, and its settings. */
function Explain({ issue }: { issue: IssueDetail }) {
  const r = issue.rule;
  if (!r) return null;
  const params = Object.entries(r.params);
  return (
    <details className="group mt-3 rounded-2xl border border-white/10 bg-white/[0.03] text-sm">
      <summary className="cursor-pointer list-none rounded-2xl px-4 py-3 font-semibold text-saffron hover:bg-white/[0.04] focus-visible:outline-2 focus-visible:outline-saffron">
        <span className="mr-1 inline-block transition group-open:rotate-90" aria-hidden>▸</span> Why was this flagged? How Rsafe decided
      </summary>
      <div className="grid gap-3 px-4 pb-4 text-cream">
        <p>
          Rule <span className="font-mono">{r.id}</span> version <span className="font-mono">{r.version}</span> ran its check{" "}
          <span className="font-mono text-violet">{r.check}</span> on{" "}
          {r.scope === "dataset" ? "all records together (needed to find duplicates)" : "this record on its own"}.
          {r.hold && " Its issues start held: the flagged change is never applied until a person decides."}
        </p>
        <div>
          <p className="text-xs uppercase tracking-wider text-mist">Data it read</p>
          <ul className="mt-1 list-disc pl-5 text-mist">
            {r.uses.map((u) => <li key={u}>{u}</li>)}
          </ul>
        </div>
        {params.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-wider text-mist">Settings in the rule file</p>
            <p className="mt-1 font-mono text-xs text-mist">{params.map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(" · ")}</p>
          </div>
        )}
        <p className="text-xs text-mist">
          The values it used for this record are under Evidence. Raised {formatTime(issue.created_at)}; severity {r.severity}
          {r.addresses ? `; addresses "${r.addresses}"` : ""}. Rules are read-only YAML files, listed on the Rules screen.
        </p>
      </div>
    </details>
  );
}

export function IssuePanel({ issueId, onClose, onChanged }: Props) {
  const me = useIdentity();
  const toast = useToast();
  const { rule: ruleText } = useLang();
  const { data: issue, error, loading, reload } = useApi<IssueDetail>(issueId ? `/issues/${issueId}` : null);
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [field, setField] = useState("");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    setNote("");
    setEditing(false);
  }, [issueId]);

  useEffect(() => {
    if (!issue) return;
    const f = issue.suggested_field ?? issue.editable_fields.find((x) => x in issue.evidence) ?? issue.editable_fields[0] ?? "";
    setField(f);
    setValue(issue.suggested_value ?? String(issue.record[f] ?? ""));
  }, [issue]);

  const act = async (action: Action) => {
    if (!issue) return;
    setBusy(action);
    try {
      const body = action === "edit" ? { field, value, note } : { note };
      const r = await post<ActionResult>(`/issues/${issue.id}/${action}`, body);
      const stillThere = action !== "reject-suggestion" && (r.issue.status === "open" || (action !== "hold" && r.issue.status === "held"));
      toast(
        stillThere
          ? { kind: "info", title: "Saved, but the problem is still there", body: `Audit entry #${r.audit_id}. Re-check the value.` }
          : { kind: "success", title: action === "hold" ? "Held for review" : action === "reject-suggestion" ? "Suggestion rejected" : "Saved", body: `Written to the audit log as entry #${r.audit_id}.` },
      );
      setEditing(false);
      onChanged(r);
      reload();
    } catch (e) {
      toast({ kind: "error", title: "Not saved", body: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  const actionable = issue && (issue.status === "open" || issue.status === "held");
  const mayAct = can.act(me.role) && !(me.role === "teacher" && issue?.status === "held");
  const evidenceKeys = issue ? Object.keys(issue.evidence) : [];
  const t = issue ? ruleText(issue.rule_id, { title: issue.title, message: issue.message, fix: issue.fix }) : null;
  const hasSuggestion = !!issue && issue.suggested_value !== null && !!issue.suggested_field;
  const relevant = new Set([issue?.suggested_field, ...evidenceKeys].filter(Boolean) as string[]);

  const footer =
    issue && actionable && mayAct ? (
      <>
        {can.hold(me.role) && issue.status !== "held" && (
          <Button variant="ghost" icon={<PauseCircle className="h-4 w-4" aria-hidden />} loading={busy === "hold"} disabled={!!busy} onClick={() => act("hold")}>
            Hold
          </Button>
        )}
        <Button variant="ghost" icon={<PencilLine className="h-4 w-4" aria-hidden />} disabled={!!busy || issue.editable_fields.length === 0} onClick={() => setEditing((x) => !x)} aria-expanded={editing}>
          Edit
        </Button>
        <Button icon={<Check className="h-4 w-4" aria-hidden />} loading={busy === "approve"} disabled={!!busy} onClick={() => act("approve")}>
          {issue.suggested_value !== null ? "Approve fix" : issue.status === "held" ? "Confirm flag" : "Confirm record is right"}
        </Button>
      </>
    ) : undefined;

  return (
    <SidePanel
      open={issueId !== null}
      onClose={onClose}
      title={issue && t ? `${issue.rule_id} · ${t.title}` : "Issue"}
      footer={footer}
    >
      {loading && !issue && <Loading label="Loading issue" />}
      {error && <ErrorNote error={error} onRetry={reload} />}
      {issue && (
        <div>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <SeverityBadge severity={issue.severity} />
            <StatusPill status={issue.status === "resolved" ? "verified" : issue.status} label={issue.status === "resolved" ? "Resolved" : undefined} />
            <span className="rounded-full bg-white/10 px-2.5 py-0.5 font-mono text-xs text-cream">
              {issue.rule_id} v{issue.rule_version}
            </span>
            <span className="text-xs text-mist">
              {humanise(issue.entity)} {issue.entity_ref} · {issue.school_code}
            </span>
          </div>

          {issue.status === "held" && (
            <div className="mb-5 flex gap-3 rounded-2xl border border-coral/40 bg-coral/10 p-4 text-sm">
              <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-coral" aria-hidden />
              <p className="text-cream">
                Held for a person to review. Rsafe has not applied this flag and has not changed the record.
                {me.role === "teacher" && " Only the principal can release it."}
              </p>
            </div>
          )}

          <Section title="Why this was flagged">
            <p className="text-base leading-relaxed text-cream" lang={htmlLang(t!.lang)}>{t!.message}</p>
            <MachineNote className="mt-1" />
            <p className="mt-2 text-sm leading-relaxed text-mist">{issue.detail}</p>
            {issue.confidence && !hasSuggestion && (
              <p className="mt-3 flex gap-2 rounded-xl bg-violet/10 p-3 text-sm text-cream">
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-violet" aria-hidden />
                <span>
                  <span className="font-semibold text-violet">Confidence. </span>
                  {issue.confidence}
                </span>
              </p>
            )}
            {issue.rule?.addresses && <p className="mt-2 text-xs text-mist">Addresses: {issue.rule.addresses}</p>}
            <Explain issue={issue} />
          </Section>

          <Section title="Evidence">
            <dl className="grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1.5 rounded-2xl bg-white/[0.04] p-4 text-sm">
              {evidenceKeys.map((k) => (
                <div key={k} className="contents">
                  <dt className="text-mist">{humanise(k)}</dt>
                  <dd className="break-words text-cream">{formatValue(issue.evidence[k])}</dd>
                </div>
              ))}
            </dl>
          </Section>

          <Section title="Current record">
            <dl className="grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1 rounded-2xl bg-white/[0.04] p-4 text-sm">
              {Object.entries(issue.record).map(([k, v]) => (
                <div key={k} className={cn("contents", relevant.has(k) && "[&>*]:text-saffron")}>
                  <dt className="text-mist">{humanise(k)}</dt>
                  <dd className="break-words font-medium text-cream">
                    {formatValue(v)}
                    {relevant.has(k) && <span className="sr-only"> (relevant to this issue)</span>}
                  </dd>
                </div>
              ))}
            </dl>
          </Section>

          <Section title="Suggested fix">
            <p className="text-sm leading-relaxed text-cream" lang={htmlLang(t!.lang)}>{t!.fix}</p>
            {hasSuggestion && (
              <div className="mt-3 rounded-2xl border border-aqua/30 bg-aqua/[0.06] p-4">
                <p className="mb-2 text-xs text-mist">Suggested {humanise(issue.suggested_field!).toLowerCase()}</p>
                <WordDiff from={String(issue.record[issue.suggested_field!] ?? "")} to={issue.suggested_value!} />
                {issue.confidence && (
                  <p className="mt-3 flex gap-2 text-sm text-cream">
                    <Info className="mt-0.5 h-4 w-4 shrink-0 text-violet" aria-hidden />
                    <span><span className="font-semibold text-violet">Why this value: </span>{issue.confidence}</span>
                  </p>
                )}
                {actionable && mayAct && (
                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-white/10 pt-3">
                    <span className="text-xs text-mist">Wrong suggestion? Reject it, then edit the value or confirm the record.</span>
                    <Button size="sm" variant="ghost" icon={<ThumbsDown className="h-4 w-4" aria-hidden />} loading={busy === "reject-suggestion"}
                      disabled={!!busy} onClick={() => act("reject-suggestion")}>
                      Reject suggestion
                    </Button>
                  </div>
                )}
              </div>
            )}
          </Section>

          {issue.history.length > 0 && (
            <Section title="History">
              <ol className="grid gap-2">
                {issue.history.map((h) => (
                  <li key={h.id} className="flex gap-3 rounded-xl bg-white/[0.04] p-3 text-sm">
                    <History className="mt-0.5 h-4 w-4 shrink-0 text-mist" aria-hidden />
                    <div>
                      <p className="text-cream">
                        {HISTORY_LABEL[h.action] ?? humanise(h.action)}
                        {h.rejected_value && <> (<span className="line-through">{h.rejected_value}</span>)</>}
                        {h.field && h.new !== null && <>: {humanise(h.field)} → {String(h.new)}</>}
                      </p>
                      <p className="text-xs text-mist">{h.actor} · {formatTime(h.ts)} · audit #{h.id}{h.note && ` · "${h.note}"`}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </Section>
          )}

          {actionable && mayAct && (
            <Section title="Your decision">
              {editing && (
                <div className="mb-3 grid gap-3 rounded-2xl bg-white/[0.04] p-4 sm:grid-cols-2">
                  <label className="flex flex-col gap-1 text-xs text-mist">
                    Field
                    <select value={field} onChange={(e) => { setField(e.target.value); setValue(String(issue.record[e.target.value] ?? "")); }}
                      className="h-10 rounded-xl border border-white/15 bg-bg-mid/70 px-3 text-sm text-cream focus-visible:outline-2 focus-visible:outline-saffron">
                      {issue.editable_fields.map((f) => <option key={f} value={f}>{humanise(f)}</option>)}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-xs text-mist">
                    New value {FIELD_HINT[field] && <span>({FIELD_HINT[field]})</span>}
                    <input value={value} onChange={(e) => setValue(e.target.value)} maxLength={200}
                      className="h-10 rounded-xl border border-white/15 bg-bg-mid/70 px-3 text-sm text-cream focus-visible:outline-2 focus-visible:outline-saffron" />
                  </label>
                  <div className="sm:col-span-2 flex justify-end">
                    <Button size="sm" loading={busy === "edit"} disabled={!!busy || !value.trim()} onClick={() => act("edit")}>Save edit</Button>
                  </div>
                </div>
              )}
              <label className="flex flex-col gap-1 text-xs text-mist">
                Note for the audit log (optional)
                <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={2}
                  placeholder="For example: checked against the birth certificate"
                  className="rounded-xl border border-white/15 bg-bg-mid/70 p-3 text-sm text-cream placeholder:text-mist/70 focus-visible:outline-2 focus-visible:outline-saffron" />
              </label>
            </Section>
          )}

          {!actionable && (
            <p className="rounded-2xl bg-white/[0.05] p-4 text-sm text-cream">
              {issue.status === "resolved"
                ? "Resolved: the problem no longer appears when the rules run."
                : `${humanise(issue.status)} by ${issue.acted_by ?? "someone"}.`}
              {issue.note && <span className="mt-1 block text-mist">Note: {issue.note}</span>}
            </p>
          )}
          {actionable && !mayAct && !can.act(me.role) && (
            <p className="rounded-2xl bg-white/[0.05] p-4 text-sm text-mist">Your role can view this issue but not change records.</p>
          )}
        </div>
      )}
    </SidePanel>
  );
}
