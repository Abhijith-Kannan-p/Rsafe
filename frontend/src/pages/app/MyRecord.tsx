import { AlertTriangle, CheckCircle2, Clock3, FlaskConical, MessageSquareWarning, Smartphone, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { Button, GlassCard, useToast } from "../../components";
import { ErrorNote, formatTime, Loading, PageHeader } from "../../components/ui";
import { post, type Confirmation, type MyRecord as Rec } from "../../lib/api";
import { cn } from "../../lib/cn";
import { htmlLang, LanguageSelect, MachineNote, useLang } from "../../lib/i18n";
import { useApi } from "../../lib/useApi";

type Step = "ask" | "otp" | "done";
type Start = { mock: boolean; sent_to: string; demo_code: string; note: string };

const GENDER: Record<string, string> = { M: "Male", F: "Female", T: "Transgender" };

function ConfirmFlow({ onDone }: { onDone: (c: Confirmation) => void }) {
  const toast = useToast();
  const [step, setStep] = useState<Step>("ask");
  const [outcome, setOutcome] = useState<"correct" | "needs_change" | null>(null);
  const [comment, setComment] = useState("");
  const [start, setStart] = useState<Start | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [auditId, setAuditId] = useState<number | null>(null);

  const sendCode = async () => {
    setBusy(true);
    try {
      setStart(await post<Start>("/my/confirm/start"));
      setStep("otp");
    } catch (e) {
      toast({ kind: "error", title: "Could not start", body: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await post<{ audit_id: number; confirmation: Confirmation }>("/my/confirm", { code, outcome, comment });
      setAuditId(r.audit_id);
      setStep("done");
      onDone(r.confirmation);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <GlassCard className="relative overflow-hidden" aria-labelledby="confirm-title">
      <div className="absolute right-0 top-0 flex items-center gap-1.5 rounded-bl-2xl bg-violet px-3 py-1 text-xs font-bold uppercase tracking-wider text-ink">
        <FlaskConical className="h-3.5 w-3.5" aria-hidden /> Mockup
      </div>
      <h2 id="confirm-title" className="font-display text-xl font-semibold text-cream">Confirm details</h2>
      <p className="mt-1 text-sm text-mist">
        A mockup of the planned parent confirmation. No SMS is sent and nothing in the record changes; your answer is
        saved for the school to read.
      </p>

      <ol className="mt-4 flex gap-2 text-xs" aria-label="Steps">
        {(["ask", "otp", "done"] as Step[]).map((s, i) => (
          <li key={s} aria-current={step === s ? "step" : undefined}
            className={cn("rounded-full px-3 py-1", step === s ? "bg-saffron text-ink font-semibold" : "bg-white/10 text-mist")}>
            {i + 1}. {s === "ask" ? "Check" : s === "otp" ? "Verify" : "Done"}
          </li>
        ))}
      </ol>

      {step === "ask" && (
        <div className="mt-5">
          <p className="text-cream">Are the details above correct?</p>
          <div className="mt-3 flex flex-wrap gap-3" role="radiogroup" aria-label="Are the details correct?">
            <button type="button" role="radio" aria-checked={outcome === "correct"} onClick={() => setOutcome("correct")}
              className={cn("flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold ring-1 ring-inset transition focus-visible:outline-2 focus-visible:outline-saffron",
                outcome === "correct" ? "bg-aqua/20 text-aqua ring-aqua" : "bg-white/5 text-cream ring-white/15 hover:bg-white/10")}>
              <ThumbsUp className="h-4 w-4" aria-hidden /> Yes, all correct
            </button>
            <button type="button" role="radio" aria-checked={outcome === "needs_change"} onClick={() => setOutcome("needs_change")}
              className={cn("flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold ring-1 ring-inset transition focus-visible:outline-2 focus-visible:outline-saffron",
                outcome === "needs_change" ? "bg-coral/20 text-coral ring-coral" : "bg-white/5 text-cream ring-white/15 hover:bg-white/10")}>
              <ThumbsDown className="h-4 w-4" aria-hidden /> Something is wrong
            </button>
          </div>
          {outcome === "needs_change" && (
            <label className="mt-4 flex flex-col gap-1 text-sm text-mist">
              What should change? (do not type ID numbers)
              <textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={300} rows={3}
                placeholder="For example: the name should be Ananya R. Kumar, as on the birth certificate"
                className="rounded-xl border border-white/15 bg-bg-mid/70 p-3 text-cream placeholder:text-mist/70 focus-visible:outline-2 focus-visible:outline-saffron" />
            </label>
          )}
          <Button className="mt-4" disabled={!outcome || (outcome === "needs_change" && !comment.trim())} loading={busy} onClick={sendCode}
            icon={<Smartphone className="h-4 w-4" aria-hidden />}>
            Send me a code
          </Button>
        </div>
      )}

      {step === "otp" && start && (
        <div className="mt-5 max-w-md">
          <p className="text-cream">We sent a 6-digit code to the {start.sent_to}.</p>
          <p className="mt-3 rounded-xl border border-dashed border-violet/60 bg-violet/10 p-3 text-sm text-cream">
            <span className="font-semibold text-violet">Demo code: </span>
            <span className="font-mono text-lg tracking-[0.3em]">{start.demo_code}</span>
            <span className="mt-1 block text-xs text-mist">{start.note}</span>
          </p>
          <label className="mt-4 flex flex-col gap-1 text-sm text-mist">
            Enter the code
            <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric" autoComplete="one-time-code" aria-invalid={!!err} aria-describedby={err ? "otp-err" : undefined}
              className="h-14 w-56 rounded-2xl border border-white/20 bg-bg-mid/70 text-center font-mono text-2xl tracking-[0.5em] text-cream focus-visible:outline-2 focus-visible:outline-saffron" />
          </label>
          {err && <p id="otp-err" role="alert" className="mt-2 text-sm text-coral">{err}</p>}
          <div className="mt-4 flex gap-3">
            <Button variant="ghost" onClick={() => setStep("ask")}>Back</Button>
            <Button disabled={code.length !== 6} loading={busy} onClick={verify}>Verify and send</Button>
          </div>
        </div>
      )}

      {step === "done" && (
        <div className="mt-5 flex gap-3 rounded-2xl bg-aqua/10 p-4" role="status">
          <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0 text-aqua" aria-hidden />
          <div className="text-sm">
            <p className="font-semibold text-cream">Thank you. Your answer reached the school.</p>
            <p className="text-mist">
              Saved as audit entry #{auditId}. Nothing in the record was changed; a staff member will review it.
            </p>
          </div>
        </div>
      )}
    </GlassCard>
  );
}

export function MyRecord() {
  const data = useApi<Rec>("/my/record");
  const { rule } = useLang();
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  if (data.loading && !data.data) return <Loading label="Loading the record" />;
  if (data.error) return <ErrorNote error={data.error} onRetry={data.reload} />;
  const d = data.data!;
  const st = d.student;
  const active = d.issues.filter((i) => i.status === "open" || i.status === "held");
  const last = confirmation ?? d.confirmation;

  const rows: [string, string][] = [
    ["Name", st.name || "(empty)"],
    ["Class", `${st.class_grade ?? "?"}${st.section}`],
    ["Date of birth", st.dob || "(empty)"],
    ["Gender", GENDER[st.gender] ?? (st.gender || "(empty)")],
    ["Guardian", st.guardian_name || "(empty)"],
    ["Aadhaar", st.aadhaar ? `${st.aadhaar} (${st.aadhaar_status.replace("_", " ")})` : `Not recorded (${st.aadhaar_status || "missing"})`],
    ["Enrolment", st.enrolment_status],
  ];

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="My record" subtitle={`${d.school.name} (${d.school.code}). This is what the school will submit for your child.`} />

      <div className={cn("glass mb-4 flex items-start gap-3 p-5", active.length ? "!bg-saffron/[0.08]" : "!bg-aqua/[0.08]")}>
        {active.length ? <AlertTriangle className="mt-0.5 h-6 w-6 shrink-0 text-saffron" aria-hidden /> : <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0 text-aqua" aria-hidden />}
        <div>
          <p className="font-display text-lg font-semibold text-cream">
            {active.length ? `${active.length} thing${active.length > 1 ? "s" : ""} the school is checking` : "Everything looks right"}
          </p>
          <p className="text-sm text-mist">
            {active.length ? "You don't need to do anything unless a detail below is wrong." : "No problems were found in this record."}
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <GlassCard aria-labelledby="details-title">
          <h2 id="details-title" className="mb-3 font-display text-lg font-semibold text-cream">Details on file</h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
            {rows.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-mist">{k}</dt>
                <dd className="font-medium text-cream">{v}</dd>
              </div>
            ))}
          </dl>
        </GlassCard>

        <GlassCard aria-labelledby="checks-title">
          <h2 id="checks-title" className="mb-3 font-display text-lg font-semibold text-cream">What the school is checking</h2>
          {d.issues.length === 0 && <p className="text-sm text-mist">Nothing.</p>}
          <ul className="grid gap-3">
            {d.issues.map((i) => {
              const done = !(i.status === "open" || i.status === "held");
              const t = rule(i.rule_id, { title: i.title, message: i.message, fix: i.fix });
              return (
                <li key={i.id} className={cn("rounded-2xl p-3", done ? "bg-aqua/[0.07]" : "bg-white/[0.05]")}>
                  <p className="flex items-center gap-2 text-sm font-semibold text-cream">
                    {done ? <CheckCircle2 className="h-4 w-4 text-aqua" aria-hidden /> : <Clock3 className="h-4 w-4 text-saffron" aria-hidden />}
                    <span lang={htmlLang(t.lang)}>{t.title}</span>
                    <span className="ml-auto text-xs font-normal text-mist">{done ? "Sorted" : i.status === "held" ? "Under review" : "Being checked"}</span>
                  </p>
                  <p className="mt-1 text-sm text-mist" lang={htmlLang(t.lang)}>{t.message}</p>
                </li>
              );
            })}
          </ul>
          {d.issues.length > 0 && <MachineNote className="mt-3" />}
          <div className="mt-3"><LanguageSelect /></div>
        </GlassCard>
      </div>

      {last && (
        <p className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-mist">
          <MessageSquareWarning className="h-4 w-4 text-violet" aria-hidden />
          Last reply: {last.outcome === "correct" ? "details confirmed" : `asked for a change ("${last.comment}")`} on {formatTime(last.ts)}.
          {last.outcome === "needs_change" &&
            (last.handled ? (
              <span className="text-aqua">The school marked it as handled on {formatTime(last.handled.ts)}.</span>
            ) : (
              <span>The school has not handled it yet.</span>
            ))}
        </p>
      )}

      <div className="mt-4">
        <ConfirmFlow onDone={setConfirmation} />
      </div>
    </div>
  );
}
