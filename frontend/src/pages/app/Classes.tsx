import { CheckCircle2, UserRound } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { GlassCard } from "../../components";
import { IssuePanel } from "../../components/IssuePanel";
import { ErrorNote, Loading, PageHeader } from "../../components/ui";
import type { IssueBrief, MyClasses } from "../../lib/api";
import { cn } from "../../lib/cn";
import { useApi } from "../../lib/useApi";

const ACTIVE = new Set(["open", "held"]);

function IssueChip({ i, onOpen }: { i: IssueBrief; onOpen: (id: number) => void }) {
  const active = ACTIVE.has(i.status);
  const tone = !active
    ? "bg-aqua/10 text-aqua ring-aqua/30"
    : i.status === "held"
      ? "bg-coral/15 text-coral ring-coral/40"
      : i.severity === "high"
        ? "bg-coral/15 text-coral ring-coral/40"
        : i.severity === "medium"
          ? "bg-saffron/15 text-saffron ring-saffron/40"
          : "bg-violet/15 text-violet ring-violet/40";
  return (
    <button
      type="button"
      onClick={() => onOpen(i.id)}
      title={`${i.title} (${i.status})`}
      aria-label={`${i.rule_id}: ${i.title}, ${i.status}. Open`}
      className={cn("rounded-full px-2.5 py-0.5 font-mono text-xs font-semibold ring-1 ring-inset transition hover:brightness-125 focus-visible:outline-2 focus-visible:outline-saffron", tone, !active && "line-through decoration-aqua/60")}
    >
      {i.rule_id}
      {i.status === "held" && " · held"}
    </button>
  );
}

export function Classes() {
  const [params, setParams] = useSearchParams();
  const data = useApi<MyClasses>("/my/classes");
  const openIssue = params.get("issue") ? Number(params.get("issue")) : null;
  const open = (id: number) => setParams({ issue: String(id) }, { replace: true });

  if (data.loading && !data.data) return <Loading label="Loading your classes" />;
  if (data.error) return <ErrorNote error={data.error} onRetry={data.reload} />;
  const d = data.data!;
  const total = d.classes.reduce((a, c) => a + c.active, 0);

  return (
    <div>
      <PageHeader
        title="My classes"
        subtitle={`${d.teacher.name} · qualified in ${d.teacher.subjects.join(", ") || "(none recorded)"} · ${d.school_code}. You see only the students you teach.`}
      />

      <GlassCard padding="sm" className="mb-4 flex flex-wrap items-center gap-3">
        <p className="px-2 text-sm text-cream">
          <span className="font-display text-2xl font-bold text-saffron">{total}</span> problem{total === 1 ? "" : "s"} to check across{" "}
          {d.classes.length} class{d.classes.length === 1 ? "" : "es"}.
        </p>
        <p className="px-2 text-xs text-mist">Click a rule code to see why and fix it. Held dropout flags can only be released by the principal.</p>
      </GlassCard>

      {d.own_issues.length > 0 && (
        <GlassCard padding="sm" className="mb-4 !bg-violet/[0.08]">
          <p className="flex flex-wrap items-center gap-2 px-2 text-sm text-cream">
            <UserRound className="h-4 w-4 text-violet" aria-hidden /> About your own record:
            {d.own_issues.map((i) => (
              <span key={i.id} className="inline-flex items-center gap-2">
                <IssueChip i={i} onOpen={open} /> <span className="text-mist">{i.title}</span>
              </span>
            ))}
          </p>
        </GlassCard>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
        {d.classes.map((c) => (
          <GlassCard key={`${c.class_grade}${c.section}`} padding="none" aria-labelledby={`class-${c.class_grade}${c.section}`}>
            <div className="flex flex-wrap items-baseline gap-3 border-b border-white/10 p-4">
              <h2 id={`class-${c.class_grade}${c.section}`} className="font-display text-xl font-bold text-cream">
                Class {c.class_grade}
                {c.section}
              </h2>
              <span className="text-sm text-mist">{c.subjects.join(", ")}</span>
              <span className={cn("ml-auto text-sm font-semibold", c.active ? "text-saffron" : "text-aqua")}>
                {c.active ? `${c.active} to check` : "All clear"}
              </span>
            </div>
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Students in class {c.class_grade}{c.section}</caption>
              <thead>
                <tr className="text-xs uppercase tracking-wider text-mist">
                  <th scope="col" className="px-4 py-2 font-semibold">Student</th>
                  <th scope="col" className="px-4 py-2 font-semibold">Date of birth</th>
                  <th scope="col" className="px-4 py-2 font-semibold">Issues</th>
                </tr>
              </thead>
              <tbody>
                {c.students.map((s) => (
                  <tr key={s.student_ref} className={cn("border-t border-white/5", s.active > 0 && "bg-saffron/[0.04]")}>
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-cream">{s.name || <span className="italic text-coral">(no name)</span>}</p>
                      <p className="font-mono text-xs text-mist">{s.student_ref}</p>
                    </td>
                    <td className="px-4 py-2.5 text-cream">{s.dob || <span className="text-mist">(empty)</span>}</td>
                    <td className="px-4 py-2.5">
                      {s.issues.length === 0 ? (
                        <span className="inline-flex items-center gap-1 text-xs text-aqua">
                          <CheckCircle2 className="h-4 w-4" aria-hidden /> No problems
                        </span>
                      ) : (
                        <div className="flex flex-wrap gap-1.5">
                          {s.issues.map((i) => (
                            <IssueChip key={i.id} i={i} onOpen={open} />
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassCard>
        ))}
      </div>

      <IssuePanel issueId={openIssue} onClose={() => setParams({}, { replace: true })} onChanged={data.reload} />
    </div>
  );
}
