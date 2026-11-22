import { ArrowLeftRight, Fingerprint, ShieldCheck } from "lucide-react";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { GlassCard, StatusPill } from "../../components";
import { IssuePanel } from "../../components/IssuePanel";
import { ErrorNote, Loading, PageHeader } from "../../components/ui";
import type { Issue } from "../../lib/api";
import { useApi } from "../../lib/useApi";

type Side = { school_code: string; student_ref: string; issue?: Issue };
type Group = { token: string; last4: string; sides: Side[] };

/** Build one group per token from the STU-006 / STU-007 issues this role can see. */
function group(issues: Issue[], otherKey: "matches" | "other_refs"): Group[] {
  const byToken = new Map<string, Group>();
  for (const i of issues) {
    const token = String(i.evidence.token ?? "");
    if (!token) continue;
    const g = byToken.get(token) ?? { token, last4: String(i.evidence.aadhaar_last4 ?? ""), sides: [] };
    const add = (s: Side) => {
      const existing = g.sides.find((x) => x.student_ref === s.student_ref);
      if (existing) existing.issue ??= s.issue;
      else g.sides.push(s);
    };
    add({ school_code: i.school_code, student_ref: i.entity_ref, issue: i });
    if (otherKey === "matches") {
      for (const m of (i.evidence.matches as { school_code: string; student_ref: string }[]) ?? []) add(m);
    } else {
      for (const ref of (i.evidence.other_refs as string[]) ?? []) add({ school_code: i.school_code, student_ref: ref });
    }
    byToken.set(token, g);
  }
  return [...byToken.values()].map((g) => ({ ...g, sides: g.sides.sort((a, b) => a.school_code.localeCompare(b.school_code)) }));
}

function TokenChip({ token, last4 }: { token: string; last4: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-violet/15 text-violet ring-1 ring-inset ring-violet/30">
        <Fingerprint className="h-5 w-5" aria-hidden />
      </span>
      <div>
        <p className="font-mono text-base text-cream">
          {token}
          <span className="text-mist">…</span>
        </p>
        <p className="text-xs text-mist">Aadhaar ending {last4 || "?"}</p>
      </div>
    </div>
  );
}

function SideCard({ side, onOpen }: { side: Side; onOpen: (id: number) => void }) {
  const inner = (
    <>
      <p className="font-display text-lg font-semibold text-cream">{side.school_code}</p>
      <p className="font-mono text-xs text-mist">{side.student_ref}</p>
      <div className="mt-2">
        {side.issue ? <StatusPill status={side.issue.status === "resolved" ? "verified" : side.issue.status} /> : <span className="text-xs text-mist">Not in your scope</span>}
      </div>
    </>
  );
  return side.issue ? (
    <button
      type="button"
      onClick={() => onOpen(side.issue!.id)}
      className="flex-1 rounded-2xl bg-white/[0.05] p-4 text-left transition hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-saffron"
      aria-label={`Open issue for ${side.student_ref} at ${side.school_code}`}
    >
      {inner}
    </button>
  ) : (
    <div className="flex-1 rounded-2xl border border-dashed border-white/15 p-4">{inner}</div>
  );
}

export function Duplicates() {
  const [params, setParams] = useSearchParams();
  const cross = useApi<Issue[]>("/issues?rule_id=STU-007");
  const within = useApi<Issue[]>("/issues?rule_id=STU-006");
  const crossGroups = useMemo(() => group(cross.data ?? [], "matches"), [cross.data]);
  const withinGroups = useMemo(() => group(within.data ?? [], "other_refs"), [within.data]);
  const openIssue = params.get("issue") ? Number(params.get("issue")) : null;
  const open = (id: number) => setParams({ issue: String(id) }, { replace: true });

  return (
    <div>
      <PageHeader title="Duplicates" subtitle="Students enrolled more than once, matched by keyed token. Names are never used to match." />

      <GlassCard padding="sm" className="mb-4 flex items-start gap-3 !bg-aqua/[0.06]">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-aqua" aria-hidden />
        <p className="text-sm text-cream">
          Each school turns Aadhaar numbers into tokens with its own key. A separate cluster key makes a matching token so the
          same child can be found in two schools without either school seeing the other's raw IDs. Shown here: the first six
          characters of the token and the last four digits.
        </p>
      </GlassCard>

      {(cross.error || within.error) && <ErrorNote error={(cross.error ?? within.error)!} onRetry={() => { cross.reload(); within.reload(); }} />}

      <h2 className="mb-3 mt-6 font-display text-xl font-semibold text-cream">Across schools (STU-007)</h2>
      {cross.loading && !cross.data ? (
        <Loading />
      ) : crossGroups.length === 0 ? (
        <p className="text-mist">No student appears in two schools.</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {crossGroups.map((g) => (
            <GlassCard key={g.token}>
              <TokenChip token={g.token} last4={g.last4} />
              <div className="mt-4 flex items-stretch gap-3">
                {g.sides.map((s, i) => (
                  <div key={s.student_ref} className="contents">
                    {i > 0 && <ArrowLeftRight className="h-5 w-5 shrink-0 self-center text-saffron" aria-label="matches" />}
                    <SideCard side={s} onOpen={open} />
                  </div>
                ))}
              </div>
              <p className="mt-3 text-xs text-mist">Matched on the cluster token. Confidence high: identical token means the same Aadhaar number.</p>
            </GlassCard>
          ))}
        </div>
      )}

      <h2 className="mb-3 mt-8 font-display text-xl font-semibold text-cream">Within one school (STU-006)</h2>
      {within.loading && !within.data ? (
        <Loading />
      ) : withinGroups.length === 0 ? (
        <p className="text-mist">No student appears twice in the same school.</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {withinGroups.map((g) => (
            <GlassCard key={g.token}>
              <TokenChip token={g.token} last4={g.last4} />
              <div className="mt-4 flex items-stretch gap-3">
                {g.sides.map((s, i) => (
                  <div key={s.student_ref} className="contents">
                    {i > 0 && <ArrowLeftRight className="h-5 w-5 shrink-0 self-center text-saffron" aria-label="matches" />}
                    <SideCard side={s} onOpen={open} />
                  </div>
                ))}
              </div>
            </GlassCard>
          ))}
        </div>
      )}

      <IssuePanel
        issueId={openIssue}
        onClose={() => setParams({}, { replace: true })}
        onChanged={() => {
          cross.reload();
          within.reload();
        }}
      />
    </div>
  );
}
