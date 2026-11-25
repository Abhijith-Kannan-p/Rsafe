import { PlayCircle, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button, DataTable, GlassCard, ReadinessRing, SeverityBadge, StatusPill, useToast, type Column } from "../../components";
import { IssuePanel } from "../../components/IssuePanel";
import { ParentRequests } from "../../components/ParentRequests";
import { ErrorNote, Loading, PageHeader, Select, Stat } from "../../components/ui";
import { TrendChart } from "../../components/TrendChart";
import { overallReadiness, post, qs, type Issue, type SchoolSummary, type TrendPoint } from "../../lib/api";
import { htmlLang, useLang } from "../../lib/i18n";
import { can, useIdentity } from "../../lib/session";
import { useApi } from "../../lib/useApi";

const ACTIVE = "active";

/** Who decided an issue, as a role name ("Teacher", "Principal"). Empty when nobody has acted yet. */
function decidedBy(i: Issue): string {
  if (!i.acted_by || !["approved", "edited", "held"].includes(i.status)) return "";
  return i.acted_by.replace(/^Demo\s+/, "").replace(/\s*\(.*\)\s*$/, "") || i.acted_by;
}

export function Dashboard() {
  const me = useIdentity();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [running, setRunning] = useState(false);

  const filters = {
    status: params.get("status") ?? ACTIVE,
    severity: params.get("severity") ?? "",
    rule_id: params.get("rule") ?? "",
    entity: params.get("entity") ?? "",
    school_code: params.get("school") ?? "",
  };
  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "issue") next.delete("issue");
    setParams(next, { replace: true });
  };

  const summary = useApi<{ schools: SchoolSummary[] }>("/summary");
  const all = useApi<Issue[]>(`/issues${qs({ school_code: filters.school_code })}`);
  const { rule } = useLang();
  // the trend is per school: a principal's own, or the school picked in the filter
  const trendSchool = me.role === "principal" ? me.school_code : can.validate(me.role) ? filters.school_code : "";
  const trend = useApi<{ points: TrendPoint[] }>(trendSchool ? `/trend${qs({ school_code: trendSchool })}` : null);
  const openIssue = params.get("issue") ? Number(params.get("issue")) : null;

  const schools = useMemo(
    () => (summary.data?.schools ?? []).filter((s) => !filters.school_code || s.school_code === filters.school_code),
    [summary.data, filters.school_code],
  );
  const multiSchool = (summary.data?.schools.length ?? 0) > 1;

  const issues = useMemo(() => {
    const xs = all.data ?? [];
    return xs.filter(
      (i) =>
        (filters.status === ACTIVE ? i.status === "open" || i.status === "held" : filters.status === "all" || i.status === filters.status) &&
        (!filters.severity || i.severity === filters.severity) &&
        (!filters.rule_id || i.rule_id === filters.rule_id) &&
        (!filters.entity || i.entity === filters.entity),
    );
  }, [all.data, filters.status, filters.severity, filters.rule_id, filters.entity]);

  const active = (all.data ?? []).filter((i) => i.status === "open" || i.status === "held");
  const sev = (s: string) => active.filter((i) => i.severity === s).length;
  const held = active.filter((i) => i.status === "held");
  const ruleIds = [...new Set((all.data ?? []).map((i) => i.rule_id))].sort();

  const refresh = () => {
    summary.reload();
    all.reload();
    if (trendSchool) trend.reload();
  };

  const runValidation = async () => {
    setRunning(true);
    const t0 = performance.now();
    try {
      const r = await post<{ changes: Record<string, { added: number; resolved: number; reopened: number }> }>(
        "/validate",
        filters.school_code ? { school_code: filters.school_code } : {},
      );
      const c = Object.values(r.changes).reduce((a, x) => ({ added: a.added + x.added, resolved: a.resolved + x.resolved }), { added: 0, resolved: 0 });
      toast({
        kind: "success",
        title: `Validation finished in ${Math.round(performance.now() - t0)} ms`,
        body: `${c.added} new issue(s), ${c.resolved} resolved. Logged to the audit trail.`,
      });
      refresh();
    } catch (e) {
      toast({ kind: "error", title: "Validation failed", body: (e as Error).message });
    } finally {
      setRunning(false);
    }
  };

  const columns: Column<Issue>[] = [
    { key: "severity", header: "Severity", render: (i) => <SeverityBadge severity={i.severity} />, sortValue: (i) => ({ high: 0, medium: 1, low: 2 })[i.severity] },
    { key: "rule_id", header: "Rule", render: (i) => <span className="font-mono text-xs">{i.rule_id}</span>, sortValue: (i) => i.rule_id },
    { key: "entity_ref", header: "Record", render: (i) => <span className="whitespace-nowrap font-mono text-xs text-mist">{i.entity_ref}</span>, sortValue: (i) => i.entity_ref },
    ...(multiSchool ? [{ key: "school_code", header: "School", sortValue: (i: Issue) => i.school_code } as Column<Issue>] : []),
    {
      key: "detail",
      header: "Problem",
      render: (i) => (
        <div className="max-w-xl">
          <p className="font-medium text-cream" lang={htmlLang(rule(i.rule_id, i).lang)}>{rule(i.rule_id, i).title}</p>
          <p className="line-clamp-1 text-xs text-mist">{i.detail}</p>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (i) => {
        const by = decidedBy(i);
        return (
          <div className="flex flex-col items-start gap-1">
            <StatusPill status={i.status === "resolved" ? "verified" : i.status} label={i.status === "resolved" ? "Resolved" : undefined} />
            {by && <span className="whitespace-nowrap text-xs text-mist" title={i.acted_by ?? undefined}>by {by}</span>}
          </div>
        );
      },
      sortValue: (i) => `${i.status} ${decidedBy(i)}`,
    },
  ];

  const title = { teacher: "Issue list", mis_coordinator: "Issue list", admin: "All issues" }[me.role as string] ?? "Dashboard";
  const readiness = overallReadiness(schools);
  const students = schools.reduce((a, s) => a + s.students, 0);

  return (
    <div>
      <PageHeader
        title={title}
        subtitle={
          me.role === "teacher"
            ? "Only students in the classes assigned to you."
            : me.role === "student_parent"
              ? "The problems Rsafe found in your child's record. A staff member will fix them."
              : "Every problem the rules found, explained, with a suggested fix."
        }
        actions={
          <>
            {multiSchool && (
              <Select label="School" hideLabel value={filters.school_code} onChange={(e) => setFilter("school", e.target.value)}>
                <option value="">All schools</option>
                {summary.data?.schools.map((s) => (
                  <option key={s.school_code} value={s.school_code}>
                    {s.school_code} · {s.name}
                  </option>
                ))}
              </Select>
            )}
            {can.validate(me.role) && (
              <Button icon={<PlayCircle className="h-5 w-5" aria-hidden />} loading={running} onClick={runValidation}>
                Run validation
              </Button>
            )}
          </>
        }
      />

      {summary.error && <ErrorNote error={summary.error} onRetry={refresh} />}
      {all.error && <ErrorNote error={all.error} onRetry={refresh} />}

      <div className="grid gap-4 lg:grid-cols-[auto_1fr]">
        <GlassCard className="flex items-center gap-6" data-tour="readiness">
          <ReadinessRing value={readiness} size={164} />
          <div className="text-sm text-mist">
            <p className="text-cream">
              <span className="font-semibold">{students}</span> student {students === 1 ? "record" : "records"}
              {me.role === "teacher" && " in your classes"}
            </p>
            <p className="mt-1 max-w-[15rem] text-xs leading-relaxed">
              Share of records with no open problem; high severity counts fully, medium half, low a fifth.
            </p>
          </div>
        </GlassCard>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="High" value={sev("high")} tone="coral" hint="Blocks submission" />
          <Stat label="Medium" value={sev("medium")} tone="saffron" hint="Should be fixed" />
          <Stat label="Low" value={sev("low")} tone="violet" hint="Worth a look" />
          <Stat label="Held" value={held.length} tone="coral" hint="Waiting for a person" />
        </div>
      </div>

      {trendSchool && trend.data && (
        <GlassCard className="mt-4" padding="sm">
          <div className="px-2">
            <TrendChart points={trend.data.points} title={`Readiness over time · ${trendSchool}`} />
          </div>
        </GlassCard>
      )}

      {(me.role === "principal" || me.role === "mis_coordinator") && (
        <ParentRequests refreshKey={all.data} showSchool={multiSchool} onOpen={(id) => setFilter("issue", String(id))} />
      )}

      {held.length > 0 && (
        <GlassCard className="mt-4 border-coral/30" padding="sm" aria-labelledby="held-title" data-tour="held">
          <div className="flex items-center gap-2 px-2 pb-2">
            <ShieldAlert className="h-5 w-5 text-coral" aria-hidden />
            <h2 id="held-title" className="font-display text-lg font-semibold text-cream">
              Held dropout flags
            </h2>
            <span className="text-sm text-mist">Not applied. A person must review each one.</span>
          </div>
          <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {held.map((i) => (
              <li key={i.id}>
                <button
                  type="button"
                  onClick={() => setFilter("issue", String(i.id))}
                  className="w-full rounded-2xl bg-white/[0.05] p-3 text-left transition hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-saffron"
                >
                  <p className="flex items-center gap-2 text-sm font-medium text-cream">
                    <span className="font-mono text-xs text-coral">{i.rule_id}</span> {i.entity_ref}
                  </p>
                  <p className="mt-1 line-clamp-2 text-xs text-mist">{i.detail}</p>
                </button>
              </li>
            ))}
          </ul>
        </GlassCard>
      )}

      <GlassCard className="mt-4" padding="none" data-tour="issues">
        <div className="flex flex-wrap items-end gap-3 border-b border-white/10 p-4">
          <h2 className="mr-auto font-display text-lg font-semibold text-cream">
            Issues <span className="text-sm font-normal text-mist">({issues.length})</span>
          </h2>
          <Select label="Severity" value={filters.severity} onChange={(e) => setFilter("severity", e.target.value)}>
            <option value="">All</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </Select>
          <Select label="Rule" value={filters.rule_id} onChange={(e) => setFilter("rule", e.target.value)}>
            <option value="">All</option>
            {ruleIds.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </Select>
          <Select label="Entity" value={filters.entity} onChange={(e) => setFilter("entity", e.target.value)}>
            <option value="">All</option>
            <option value="student">Student</option>
            <option value="teacher">Teacher</option>
            <option value="facility">Facility</option>
          </Select>
          <Select label="Status" value={filters.status} onChange={(e) => setFilter("status", e.target.value === ACTIVE ? "" : e.target.value)}>
            <option value={ACTIVE}>Needs action</option>
            <option value="all">Everything</option>
            <option value="open">Open</option>
            <option value="held">Held</option>
            <option value="approved">Approved or confirmed</option>
            <option value="edited">Edited</option>
            <option value="resolved">Resolved</option>
          </Select>
        </div>
        {all.loading && !all.data ? (
          <div className="px-4">
            <Loading label="Loading issues" />
          </div>
        ) : (
          <DataTable
            caption="Issues found by the rules"
            columns={columns}
            rows={issues}
            rowKey={(i) => i.id}
            onRowClick={(i) => setFilter("issue", String(i.id))}
            rowClassName={(i) => (i.id === openIssue ? "bg-saffron/10" : undefined)}
            empty={filters.status === ACTIVE ? "Nothing needs action. This data is ready." : "No issues match these filters."}
          />
        )}
      </GlassCard>

      <IssuePanel
        issueId={openIssue}
        onClose={() => setFilter("issue", "")}
        onChanged={refresh}
      />
    </div>
  );
}
