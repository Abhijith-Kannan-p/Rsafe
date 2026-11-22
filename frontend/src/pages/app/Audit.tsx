import { AlertOctagon, CheckCircle2, ShieldCheck, Skull } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, DataTable, GlassCard, Modal, useToast, type Column } from "../../components";
import { ErrorNote, formatTime, Loading, PageHeader } from "../../components/ui";
import { post, api, type AuditRow, type ChainReport } from "../../lib/api";
import { cn } from "../../lib/cn";
import { useApi } from "../../lib/useApi";

export function Audit() {
  const toast = useToast();
  const rows = useApi<AuditRow[]>("/audit");
  const [report, setReport] = useState<ChainReport | null>(null);
  const [busy, setBusy] = useState<"verify" | "tamper" | null>(null);
  const [tampered, setTampered] = useState<number | null>(null);
  const [shown, setShown] = useState<AuditRow | null>(null);

  const verify = async () => {
    setBusy("verify");
    try {
      const r = await api<ChainReport>("/audit/verify");
      setReport(r);
      toast(r.ok ? { kind: "success", title: "Chain verified", body: `${r.checked} rows, every hash matches.` } : { kind: "error", title: `Chain broken at row #${r.first_broken_id}`, body: r.reason ?? "" });
    } catch (e) {
      toast({ kind: "error", title: "Could not verify", body: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  const tamper = async () => {
    setBusy("tamper");
    try {
      const r = await post<{ tampered_id: number; message: string }>("/audit/tamper");
      setTampered(r.tampered_id);
      setReport(null);
      rows.reload();
      toast({ kind: "info", title: `Row #${r.tampered_id} edited in the database`, body: "Now press Verify chain." });
    } catch (e) {
      toast({ kind: "error", title: "Tamper failed", body: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  const broken = report && !report.ok ? report.first_broken_id : null;
  useEffect(() => {
    if (broken) document.getElementById(`audit-${broken}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [broken]);

  const columns: Column<AuditRow>[] = [
    { key: "id", header: "#", render: (r) => <span id={`audit-${r.id}`} className="font-mono text-xs text-mist">{r.id}</span>, sortValue: (r) => r.id },
    { key: "ts", header: "Time", render: (r) => <span className="whitespace-nowrap text-xs">{formatTime(r.ts)}</span>, sortValue: (r) => r.ts },
    { key: "actor", header: "Actor", render: (r) => <span className="text-sm">{r.actor}</span>, sortValue: (r) => r.actor },
    { key: "role", header: "Role", render: (r) => <span className="text-xs text-mist">{r.role}</span> },
    { key: "action", header: "Action", render: (r) => <span className="font-mono text-xs text-saffron">{r.action}</span>, sortValue: (r) => r.action },
    { key: "record_ref", header: "Record", render: (r) => <span className="font-mono text-xs text-mist">{r.record_ref}</span> },
    {
      key: "hash",
      header: "Hash",
      render: (r) => (
        <span className={cn("font-mono text-xs", r.id === broken ? "font-bold text-coral" : "text-violet")}>
          {r.short_hash}
          {r.id === broken && <span className="ml-2 rounded bg-coral px-1.5 py-0.5 font-sans text-[10px] font-bold uppercase text-ink">Broken</span>}
        </span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Audit log"
        subtitle="Every validation, import, decision and export. Each row's hash covers the previous row's hash, so any edit breaks the chain."
        actions={
          <>
            <Button variant="danger" size="sm" icon={<Skull className="h-4 w-4" aria-hidden />} loading={busy === "tamper"} disabled={!!busy} onClick={tamper}>
              Tamper row (demo)
            </Button>
            <Button icon={<ShieldCheck className="h-5 w-5" aria-hidden />} loading={busy === "verify"} disabled={!!busy} onClick={verify}>
              Verify chain
            </Button>
          </>
        }
      />

      {report && (
        <GlassCard
          padding="sm"
          role="status"
          className={cn("mb-4 flex items-start gap-3", report.ok ? "!bg-aqua/[0.08]" : "!border-coral/50 !bg-coral/[0.12]")}
        >
          {report.ok ? <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0 text-aqua" aria-hidden /> : <AlertOctagon className="mt-0.5 h-6 w-6 shrink-0 text-coral" aria-hidden />}
          <div className="text-sm">
            <p className="font-display text-lg font-semibold text-cream">
              {report.ok ? `Chain intact: ${report.checked} rows verified` : `Tampering detected at row #${report.first_broken_id}`}
            </p>
            <p className="text-mist">
              {report.ok
                ? `Head hash ${report.head_hash?.slice(0, 16)}…`
                : `Row #${report.first_broken_id}: ${report.reason?.replace(/\.$/, "")}. ${report.checked} rows before it are intact.`}
            </p>
          </div>
        </GlassCard>
      )}
      {tampered && !report && (
        <p className="mb-4 text-sm text-mist">
          Row #{tampered} was changed directly in the database (this bypasses Rsafe, as an attacker would). Its stored hash no longer matches.
        </p>
      )}

      {rows.error && <ErrorNote error={rows.error} onRetry={rows.reload} />}
      <GlassCard padding="none">
        {rows.loading && !rows.data ? (
          <div className="px-4"><Loading label="Loading audit log" /></div>
        ) : (
          <DataTable
            caption="Audit log, newest first"
            columns={columns}
            rows={rows.data ?? []}
            rowKey={(r) => r.id}
            onRowClick={setShown}
            rowClassName={(r) => (r.id === broken ? "bg-coral/15 ring-1 ring-inset ring-coral/60" : r.id === tampered ? "bg-saffron/[0.07]" : undefined)}
          />
        )}
      </GlassCard>

      <Modal open={!!shown} onClose={() => setShown(null)} title={shown ? `Audit row #${shown.id}` : ""} className="max-w-2xl">
        {shown && (
          <div className="grid gap-3 text-sm">
            <p className="text-mist">{shown.actor} · {shown.role} · {formatTime(shown.ts)}</p>
            <pre className="max-h-80 overflow-auto rounded-2xl bg-bg-deep/80 p-4 font-mono text-xs text-cream" tabIndex={0}>
              {JSON.stringify(shown.payload, null, 2)}
            </pre>
            <p className="break-all font-mono text-xs text-mist">prev {shown.prev_hash}<br />hash {shown.hash}</p>
          </div>
        )}
      </Modal>
    </div>
  );
}
