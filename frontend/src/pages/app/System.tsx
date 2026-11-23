import { Activity, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Button, GlassCard, Modal, useToast } from "../../components";
import { ErrorNote, formatTime, Loading, PageHeader, Stat } from "../../components/ui";
import { post, type Metrics } from "../../lib/api";
import { useApi } from "../../lib/useApi";

function uptime(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h} h ${m} min` : `${m} min`;
}

/** Reset demo data: rebuilds the synthetic database and starts a new audit log. */
export function ResetDemo({ onDone, size = "md" }: { onDone?: () => void; size?: "sm" | "md" }) {
  const toast = useToast();
  const [ask, setAsk] = useState(false);
  const [busy, setBusy] = useState(false);
  const reset = async () => {
    setBusy(true);
    try {
      const r = await post<{ audit_id: number }>("/demo/reset");
      toast({ kind: "success", title: "Demo data reset", body: `Fresh synthetic data. The new audit log starts with your reset (entry #${r.audit_id}).` });
      setAsk(false);
      onDone?.();
    } catch (e) {
      toast({ kind: "error", title: "Reset failed", body: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Button variant="ghost" size={size} icon={<RotateCcw className="h-4 w-4" aria-hidden />} onClick={() => setAsk(true)}>
        Reset demo data
      </Button>
      <Modal open={ask} onClose={() => setAsk(false)} title="Reset the demo data?">
        <p className="text-sm text-cream">
          This rebuilds every school from the committed synthetic data. All decisions made since are discarded and the audit
          log starts again, beginning with a row that records your reset. It is a demo-only control.
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <Button variant="ghost" onClick={() => setAsk(false)}>Cancel</Button>
          <Button variant="danger" loading={busy} onClick={reset}>Reset now</Button>
        </div>
      </Modal>
    </>
  );
}

export function System() {
  const m = useApi<Metrics>("/metrics");
  if (m.loading && !m.data) return <Loading label="Loading system metrics" />;
  if (m.error) return <ErrorNote error={m.error} onRetry={m.reload} />;
  const d = m.data!;
  const runs = d.validation.recent_runs;
  const median = d.validation.median_ms_per_1000_records;

  return (
    <div>
      <PageHeader
        title="System"
        subtitle="Health and scalability numbers from GET /api/metrics, plus demo controls."
        actions={<ResetDemo onDone={m.reload} />}
      />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Status" value={d.status === "ok" ? "Healthy" : d.status} tone="aqua" hint={`Version ${d.version} · up ${uptime(d.uptime_s)}`} />
        <Stat label="Rules loaded" value={d.rules.loaded} hint="Versioned YAML, read-only" />
        <Stat label="Students" value={d.data.students} hint={`${d.data.schools} schools · ${d.data.teachers} teachers`} />
        <Stat
          label="Per 1,000 records"
          value={median !== null ? `${Math.round(median)} ms` : "—"}
          tone="saffron"
          hint="Median full validation, recent runs"
        />
      </div>

      <GlassCard className="mt-4" aria-labelledby="runs-title">
        <h2 id="runs-title" className="flex items-center gap-2 font-display text-lg font-semibold text-cream">
          <Activity className="h-5 w-5 text-saffron" aria-hidden /> Recent validation runs
        </h2>
        <p className="mt-1 text-sm text-mist">{d.validation.projection_note}</p>
        {runs.length === 0 ? (
          <p className="mt-3 text-sm text-mist">No timed runs yet. Run validation from the issue list.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <caption className="sr-only">Recent validation runs with timings</caption>
              <thead>
                <tr className="text-xs uppercase tracking-wider text-mist">
                  {["Audit #", "When", "Records", "Read", "Rules", "Store", "Total", "Per 1,000"].map((h) => (
                    <th key={h} scope="col" className="py-2 pr-3 font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.audit_id} className="border-t border-white/5 text-cream">
                    <td className="py-2 pr-3 font-mono text-xs text-mist">{r.audit_id}</td>
                    <td className="py-2 pr-3 text-xs">{formatTime(r.ts)}</td>
                    <td className="py-2 pr-3">{r.records.toLocaleString("en-IN")}</td>
                    <td className="py-2 pr-3">{r.read_ms} ms</td>
                    <td className="py-2 pr-3">{r.rules_ms} ms</td>
                    <td className="py-2 pr-3">{r.store_ms} ms</td>
                    <td className="py-2 pr-3 font-semibold">{r.total_ms} ms</td>
                    <td className="py-2 pr-3">{r.ms_per_1000_records ?? "—"} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-3 text-xs text-mist">
          Records counts every student, teacher and facility the rules read. For a 5,000-student measurement run{" "}
          <span className="font-mono">npm run bench</span>.
        </p>
      </GlassCard>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <GlassCard>
          <h2 className="font-display text-lg font-semibold text-cream">Issues by status</h2>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
            {Object.entries(d.issues).map(([k, v]) => (
              <div key={k} className="contents"><dt className="text-mist">{k}</dt><dd className="text-cream">{v}</dd></div>
            ))}
            <dt className="text-mist">audit rows</dt><dd className="text-cream">{d.audit_rows}</dd>
          </dl>
        </GlassCard>
        <GlassCard>
          <h2 className="font-display text-lg font-semibold text-cream">Rule versions</h2>
          <p className="mt-2 font-mono text-xs leading-relaxed text-mist">
            {Object.entries(d.rules.versions).map(([k, v]) => `${k} v${v}`).join(" · ")}
          </p>
          <p className="mt-3 text-xs text-mist">
            Raw JSON: <a href="/api/metrics" className="text-saffron hover:underline">/api/metrics</a> (public, no names or IDs).
          </p>
        </GlassCard>
      </div>
    </div>
  );
}
