import { AlertOctagon, CheckCircle2, FlaskConical, PauseCircle, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { post, type DryRun, type Verdict } from "../lib/api";
import { cn } from "../lib/cn";
import { Button } from "./Button";
import { GlassCard } from "./GlassCard";
import { useToast } from "./Toast";
import { humanise } from "./ui";

const VERDICT: Record<Verdict, { label: string; cls: string; Icon: typeof CheckCircle2; hint: string }> = {
  would_send: { label: "Would send", cls: "text-aqua bg-aqua/15 ring-aqua/40", Icon: CheckCircle2, hint: "No undecided problems" },
  would_send_flagged: { label: "Send, flagged", cls: "text-saffron bg-saffron/15 ring-saffron/40", Icon: TriangleAlert, hint: "Only medium or low problems left" },
  likely_rejected: { label: "Likely rejected", cls: "text-coral bg-coral/15 ring-coral/40", Icon: AlertOctagon, hint: "An undecided high-severity problem" },
  held_back: { label: "Held back", cls: "text-coral bg-coral/15 ring-coral/40", Icon: PauseCircle, hint: "A held flag needs a person" },
};
const ORDER: Verdict[] = ["would_send", "would_send_flagged", "likely_rejected", "held_back"];
const DECISION: Record<string, string> = { open: "open", held: "held", new: "new since last run", back: "came back", decided: "decided" };

/** Test submit: every rule runs again in memory; shows exactly what would be sent. Nothing is exported. */
export function TestSubmit({ schoolCode }: { schoolCode: string }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<DryRun | null>(null);
  const [onlyProblems, setOnlyProblems] = useState(true);

  const run = async () => {
    setBusy(true);
    try {
      setRes(await post<DryRun>("/submit/dry-run", { school_code: schoolCode }));
    } catch (e) {
      toast({ kind: "error", title: "Test submit failed", body: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const rows = useMemo(() => (res ? res.rows.filter((r) => !onlyProblems || r.verdict !== "would_send") : []), [res, onlyProblems]);
  const cols = ["student_ref", "name", "dob", "gender", "class_grade", "aadhaar_masked", "enrolment_status"];

  return (
    <GlassCard aria-labelledby="dry-title">
      <div className="flex flex-wrap items-start gap-4">
        <FlaskConical className="h-7 w-7 text-aqua" aria-hidden />
        <div className="min-w-0 flex-1">
          <h2 id="dry-title" className="font-display text-lg font-semibold text-cream">Test submit</h2>
          <p className="mt-1 text-sm text-mist">
            Runs every rule again on the current data and shows exactly what would be sent, row by row. Nothing is exported
            or changed; the check itself is noted in the audit log.
          </p>
        </div>
        <Button loading={busy} onClick={run} icon={<FlaskConical className="h-4 w-4" aria-hidden />}>
          {res ? "Run again" : "Test submit"}
        </Button>
      </div>

      {res && (
        <div className="mt-5" aria-live="polite">
          <div className={cn("flex items-start gap-3 rounded-2xl p-4", res.ready ? "bg-aqua/10" : "bg-coral/10")}>
            {res.ready ? <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0 text-aqua" aria-hidden /> : <AlertOctagon className="mt-0.5 h-6 w-6 shrink-0 text-coral" aria-hidden />}
            <div className="text-sm">
              <p className="font-display text-lg font-semibold text-cream">
                {res.ready
                  ? "Ready: no row would be rejected or held back."
                  : `Not ready: ${res.verdicts.likely_rejected + res.verdicts.held_back} of ${res.records} rows would be rejected or held back.`}
              </p>
              <p className="text-mist">
                {res.would_pass_pct}% of rows would be sent. {Object.keys(res.rules).length} rules ran in {res.ran_ms} ms. Nothing was exported.
              </p>
            </div>
          </div>

          <ul className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            {ORDER.map((v) => {
              const { label, cls, Icon, hint } = VERDICT[v];
              return (
                <li key={v} className="rounded-2xl bg-white/[0.05] p-3">
                  <p className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset", cls)}>
                    <Icon className="h-3.5 w-3.5" aria-hidden /> {label}
                  </p>
                  <p className="mt-2 font-display text-2xl font-bold text-cream">{res.verdicts[v]}</p>
                  <p className="text-xs text-mist">{hint}</p>
                </li>
              );
            })}
          </ul>

          {res.other_findings.length > 0 && (
            <p className="mt-3 text-sm text-mist">
              Also in this school's submission: {res.other_findings.map((f) => `${f.rule_id} on ${f.ref} (${DECISION[f.decision] ?? f.decision})`).join("; ")}.
            </p>
          )}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-display text-base font-semibold text-cream">What would be sent ({rows.length} rows)</h3>
            <label className="flex items-center gap-2 text-sm text-mist">
              <input type="checkbox" checked={onlyProblems} onChange={(e) => setOnlyProblems(e.target.checked)} className="h-4 w-4 accent-[#FFB43B]" />
              Only rows with problems
            </label>
          </div>
          <div className="mt-2 max-h-[28rem] overflow-auto rounded-2xl border border-white/10" tabIndex={0} aria-label="Rows that would be sent">
            <table className="w-full min-w-[56rem] text-left text-sm">
              <caption className="sr-only">Rows that would be sent, with the verdict for each</caption>
              <thead className="sticky top-0 bg-bg-mid">
                <tr className="text-xs uppercase tracking-wider text-mist">
                  <th scope="col" className="px-3 py-2 font-semibold">Verdict</th>
                  {cols.map((c) => <th key={c} scope="col" className="px-3 py-2 font-semibold">{humanise(c)}</th>)}
                  <th scope="col" className="px-3 py-2 font-semibold">Why</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const { label, cls } = VERDICT[r.verdict];
                  return (
                    <tr key={String(r.values.student_ref)} className="border-t border-white/5 align-top">
                      <td className="px-3 py-2"><span className={cn("whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset", cls)}>{label}</span></td>
                      {cols.map((c) => (
                        <td key={c} className={cn("px-3 py-2 text-cream", c === "student_ref" && "font-mono text-xs text-mist")}>
                          {r.values[c] === "" || r.values[c] === null ? <span className="text-mist/70">(empty)</span> : String(r.values[c])}
                        </td>
                      ))}
                      <td className="px-3 py-2 text-xs text-mist">
                        {r.findings.length === 0
                          ? "—"
                          : r.findings.map((f, i) => (
                              <p key={i}>
                                <span className="font-mono text-cream">{f.rule_id}</span> {f.detail}{" "}
                                <span className="text-mist/80">({DECISION[f.decision] ?? f.decision})</span>
                              </p>
                            ))}
                      </td>
                    </tr>
                  );
                })}
                {rows.length === 0 && (
                  <tr><td colSpan={cols.length + 2} className="px-3 py-6 text-center text-mist">Every row would be sent as it is.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </GlassCard>
  );
}
