import { Link } from "react-router-dom";
import { GlassCard, SeverityBadge } from "../../components";
import { ErrorNote, Loading, PageHeader } from "../../components/ui";
import type { Coverage as Cov } from "../../lib/api";
import { useApi } from "../../lib/useApi";

/** Which government-reported failure reason each rule addresses, and what it has caught so far. */
export function Coverage() {
  const data = useApi<Cov>("/coverage");
  if (data.loading && !data.data) return <Loading label="Loading rule coverage" />;
  if (data.error) return <ErrorNote error={data.error} onRetry={data.reload} />;
  const d = data.data!;
  const total = d.reasons.reduce((a, r) => a + r.found, 0);

  return (
    <div>
      <PageHeader
        title="Rule coverage"
        subtitle={`Each failure reason that gets school records rejected, the rules that catch it, and what they have found in ${
          d.schools.length === 1 ? d.schools[0] : `${d.schools.length} schools`
        }.`}
      />
      <p className="mb-4 text-sm text-mist">
        {d.reasons.length} failure reasons, {d.reasons.reduce((a, r) => a + r.rules.length, 0)} rules, {total} problems found.
        "Fixed" means a person approved or edited the value; "cleared" means the problem went away on a later run.
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        {d.reasons.map((r) => (
          <GlassCard key={r.reason} aria-labelledby={`reason-${r.reason}`}>
            <h2 id={`reason-${r.reason}`} className="font-display text-lg font-semibold text-cream">{r.reason}</h2>
            <dl className="mt-2 grid grid-cols-4 gap-2 text-center">
              {([["Found", r.found, "text-cream"], ["Still open", r.active, r.active ? "text-saffron" : "text-aqua"], ["Fixed", r.fixed, "text-aqua"], ["Cleared", r.resolved, "text-violet"]] as const).map(([k, v, cls]) => (
                <div key={k} className="rounded-xl bg-white/[0.05] p-2">
                  <dt className="text-xs text-mist">{k}</dt>
                  <dd className={`font-display text-xl font-bold ${cls}`}>{v}</dd>
                </div>
              ))}
            </dl>
            <table className="mt-3 w-full text-left text-sm">
              <caption className="sr-only">Rules that address {r.reason}</caption>
              <thead>
                <tr className="text-xs uppercase tracking-wider text-mist">
                  <th scope="col" className="py-1.5 pr-2 font-semibold">Rule</th>
                  <th scope="col" className="py-1.5 pr-2 font-semibold">Severity</th>
                  <th scope="col" className="py-1.5 pr-2 text-right font-semibold">Found</th>
                  <th scope="col" className="py-1.5 text-right font-semibold">Open</th>
                </tr>
              </thead>
              <tbody>
                {r.rules.map((x) => (
                  <tr key={x.id} className="border-t border-white/5">
                    <td className="py-2 pr-2">
                      <Link to={`/app/rules?rule=${x.id}`} className="font-mono text-xs text-saffron hover:underline focus-visible:outline-2 focus-visible:outline-saffron">
                        {x.id} v{x.version}
                      </Link>
                      <p className="text-cream">{x.title}{x.hold && <span className="ml-2 text-xs text-coral">(held for review)</span>}</p>
                    </td>
                    <td className="py-2 pr-2"><SeverityBadge severity={x.severity} /></td>
                    <td className="py-2 pr-2 text-right text-cream">{x.found}</td>
                    <td className="py-2 text-right text-cream">{x.active}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
