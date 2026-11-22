import { PauseCircle } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { DataTable, GlassCard, SeverityBadge, SidePanel, type Column } from "../../components";
import { ErrorNote, formatValue, humanise, Loading, PageHeader } from "../../components/ui";
import type { Rule, RuleDetail } from "../../lib/api";
import { useApi } from "../../lib/useApi";

export function Rules() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("rule");
  const rules = useApi<Rule[]>("/rules");
  const detail = useApi<RuleDetail>(selected ? `/rules/${selected}` : null);

  const columns: Column<Rule>[] = [
    { key: "id", header: "Rule", render: (r) => <span className="font-mono text-sm text-cream">{r.id}</span>, sortValue: (r) => r.id },
    { key: "title", header: "Checks", render: (r) => <span className="font-medium">{r.title}</span>, sortValue: (r) => r.title },
    { key: "severity", header: "Severity", render: (r) => <SeverityBadge severity={r.severity} />, sortValue: (r) => ({ high: 0, medium: 1, low: 2 })[r.severity] },
    { key: "entity", header: "Applies to", render: (r) => humanise(r.entity), sortValue: (r) => r.entity },
    { key: "version", header: "Version", render: (r) => <span className="font-mono text-xs">v{r.version}</span> },
    {
      key: "hold",
      header: "Action",
      render: (r) =>
        r.hold ? (
          <span className="inline-flex items-center gap-1 text-xs text-coral">
            <PauseCircle className="h-4 w-4" aria-hidden /> Held for review
          </span>
        ) : (
          <span className="text-xs text-mist">Flag only</span>
        ),
    },
  ];

  const d = detail.data;
  return (
    <div>
      <PageHeader title="Rules" subtitle="Versioned YAML rules loaded at startup. Read only: changing a rule means editing its file and bumping its version." />
      {rules.error && <ErrorNote error={rules.error} onRetry={rules.reload} />}
      <GlassCard padding="none">
        {rules.loading && !rules.data ? (
          <div className="px-4"><Loading label="Loading rules" /></div>
        ) : (
          <DataTable caption="Loaded rules" columns={columns} rows={rules.data ?? []} rowKey={(r) => r.id} onRowClick={(r) => setParams({ rule: r.id }, { replace: true })} />
        )}
      </GlassCard>

      <SidePanel open={!!selected} onClose={() => setParams({}, { replace: true })} title={d ? `${d.id} · ${d.title}` : selected ?? "Rule"}>
        {detail.loading && !d && <Loading />}
        {detail.error && <ErrorNote error={detail.error} />}
        {d && (
          <div className="grid gap-5 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={d.severity} />
              <span className="rounded-full bg-white/10 px-2.5 py-0.5 font-mono text-xs text-cream">v{d.version}</span>
              <span className="text-xs text-mist">{humanise(d.entity)} · {d.scope === "dataset" ? "compares records" : "one record at a time"}</span>
            </div>
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-mist">What people see</h3>
              <p className="text-cream">{d.message}</p>
              <p className="mt-2 text-mist">Fix: {d.fix}</p>
            </div>
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-mist">Government failure reason it addresses</h3>
              <p className="text-cream">{d.addresses}</p>
            </div>
            {Object.keys(d.params).length > 0 && (
              <div>
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-mist">Parameters</h3>
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                  {Object.entries(d.params).map(([k, v]) => (
                    <div key={k} className="contents"><dt className="text-mist">{humanise(k)}</dt><dd className="text-cream">{formatValue(v)}</dd></div>
                  ))}
                </dl>
              </div>
            )}
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-mist">YAML source (backend/rules/{d.id}.yaml)</h3>
              <pre className="overflow-x-auto rounded-2xl bg-bg-deep/80 p-4 font-mono text-xs leading-relaxed text-cream" tabIndex={0} aria-label={`YAML source of ${d.id}`}>
                {d.source}
              </pre>
            </div>
          </div>
        )}
      </SidePanel>
    </div>
  );
}
