import { AlertTriangle, CheckCircle2, FileSpreadsheet, FileUp, OctagonX, Sparkles } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import { Button, GlassCard, Modal, ReadinessRing, useToast } from "../../components";
import { ErrorNote, PageHeader } from "../../components/ui";
import { post, type UploadPreview, type UploadResult } from "../../lib/api";
import { cn } from "../../lib/cn";
import { useIdentity } from "../../lib/session";

const PREVIEW_COLS = ["student_ref", "name", "dob", "gender", "class_grade", "section", "aadhaar", "enrolment_status"];

export function Upload() {
  const me = useIdentity();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<{ name: string; text: string } | null>(null);
  const [preview, setPreview] = useState<UploadPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string> | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState<"preview" | "commit" | "sample" | null>(null);
  const [dragging, setDragging] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);

  const runPreview = async (f: { name: string; text: string }, m: Record<string, string> | null) => {
    setBusy("preview");
    setError(null);
    try {
      const p = await post<UploadPreview>("/upload/preview", { csv: f.text, mapping: m, filename: f.name });
      setPreview(p);
      setMapping(p.mapping);
    } catch (e) {
      setError(e as Error);
      setPreview(null);
    } finally {
      setBusy(null);
    }
  };

  const accept = async (name: string, text: string) => {
    const f = { name, text };
    setFile(f);
    setResult(null);
    await runPreview(f, null);
  };

  const onFiles = async (files: FileList | null) => {
    const f = files?.[0];
    if (!f) return;
    if (!/\.csv$/i.test(f.name)) {
      setError(new Error("Choose a .csv file. Save the spreadsheet as CSV (comma separated) first."));
      return;
    }
    accept(f.name, await f.text());
  };

  const loadSample = async () => {
    setBusy("sample");
    try {
      const name = `school_export_${me.school_code}.csv`;
      const res = await fetch(`/samples/${name}`);
      if (!res.ok) throw new Error("Sample file not found. Run `npm run seed` to create it.");
      await accept(name, await res.text());
    } catch (e) {
      setError(e as Error);
      setBusy(null);
    }
  };

  const commit = async () => {
    if (!file) return;
    setBusy("commit");
    try {
      const r = await post<UploadResult>("/upload/commit", { csv: file.text, mapping, filename: file.name });
      setResult(r);
      setConfirm(false);
      toast({ kind: "success", title: `Imported ${r.imported} records`, body: "Validation ran. Both steps are in the audit log." });
    } catch (e) {
      toast({ kind: "error", title: "Import refused", body: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    onFiles(e.dataTransfer.files);
  };

  const usedFields = new Set(Object.values(mapping ?? {}).filter(Boolean));

  return (
    <div>
      <PageHeader
        title="Upload"
        subtitle={`Import ${me.school_code}'s student file. Nothing is saved until you confirm.`}
        actions={
          <Button variant="ghost" data-tour="load-sample" icon={<Sparkles className="h-4 w-4" aria-hidden />} loading={busy === "sample"} onClick={loadSample}>
            Load sample messy file
          </Button>
        }
      />

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "glass flex flex-col items-center gap-3 border-2 border-dashed !border-white/20 p-10 text-center transition",
          dragging && "!border-saffron bg-saffron/10",
        )}
      >
        <FileUp className="h-10 w-10 text-saffron" aria-hidden />
        <p className="font-display text-lg font-semibold text-cream">
          {file ? file.name : "Drop a CSV file here"}
        </p>
        <p className="max-w-md text-sm text-mist">
          One row per student. Full Aadhaar numbers are turned into keyed tokens on arrival and never shown or stored; you
          will only see the last four digits.
        </p>
        <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" id="csv-input" aria-label="Choose a CSV file" tabIndex={-1} onChange={(e) => onFiles(e.target.files)} />
        <Button variant="ghost" size="sm" icon={<FileSpreadsheet className="h-4 w-4" aria-hidden />} loading={busy === "preview"} onClick={() => input.current?.click()}>
          Choose file
        </Button>
      </div>

      {error && (
        <div className="mt-4">
          <ErrorNote error={error} />
        </div>
      )}

      {result && (
        <GlassCard className="mt-4 flex flex-wrap items-center gap-6" aria-live="polite">
          <ReadinessRing value={result.summary.readiness} size={140} />
          <div className="flex-1 text-sm text-mist">
            <p className="flex items-center gap-2 font-display text-xl font-semibold text-cream">
              <CheckCircle2 className="h-5 w-5 text-aqua" aria-hidden /> Imported and validated
            </p>
            <p className="mt-1">
              {result.imported} records replaced {result.replaced} for {result.summary.school_code}. {result.changes.added} new issue(s),{" "}
              {result.changes.resolved} resolved, {result.changes.reopened} reopened. {result.summary.active} need action.
            </p>
          </div>
          <Link to="/app/dashboard" className="font-semibold text-saffron hover:underline">
            Review issues →
          </Link>
        </GlassCard>
      )}

      {preview && !result && (
        <>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <SummaryTile icon={FileSpreadsheet} tone="text-cream" label="Rows" value={preview.rows_total} hint={`${preview.headers.length} columns`} />
            <SummaryTile icon={OctagonX} tone="text-coral" label="Blocking errors" value={preview.counts.errors} hint="Must be fixed before import" />
            <SummaryTile icon={AlertTriangle} tone="text-saffron" label="Warnings" value={preview.counts.warnings} hint="Imported; the rules will explain them" />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[22rem_1fr]">
            <GlassCard padding="sm" aria-labelledby="map-title">
              <h2 id="map-title" className="px-2 pb-1 font-display text-lg font-semibold text-cream">Column mapping</h2>
              <p className="px-2 pb-3 text-xs text-mist">Matched from the headings. Change any that are wrong.</p>
              <ul className="grid gap-2">
                {preview.headers.map((h) => (
                  <li key={h} className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 rounded-xl bg-white/[0.04] px-3 py-2">
                    <span className="truncate text-sm text-cream" title={h}>{h}</span>
                    <span className="text-mist" aria-hidden>→</span>
                    <select
                      aria-label={`Field for column ${h}`}
                      value={mapping?.[h] ?? ""}
                      onChange={(e) => {
                        const m = { ...(mapping ?? {}), [h]: e.target.value };
                        setMapping(m);
                        if (file) runPreview(file, m);
                      }}
                      className={cn(
                        "h-9 min-w-0 rounded-lg border bg-bg-mid/70 px-2 text-sm text-cream focus-visible:outline-2 focus-visible:outline-saffron",
                        mapping?.[h] ? "border-aqua/40" : "border-white/15 text-mist",
                      )}
                    >
                      <option value="">(ignore)</option>
                      {preview.fields.map((f) => (
                        <option key={f.field} value={f.field} disabled={usedFields.has(f.field) && mapping?.[h] !== f.field}>
                          {f.label}{f.required ? " *" : ""}
                        </option>
                      ))}
                    </select>
                  </li>
                ))}
              </ul>
            </GlassCard>

            <div className="grid min-w-0 gap-4">
              <GlassCard padding="sm" aria-labelledby="prob-title">
                <h2 id="prob-title" className="px-2 pb-2 font-display text-lg font-semibold text-cream">Error summary</h2>
                {preview.file_errors.length === 0 && preview.problems.length === 0 && (
                  <p className="px-2 pb-2 text-sm text-aqua">No format problems. The rules will still check every record.</p>
                )}
                <ul className="grid max-h-60 gap-1 overflow-y-auto px-2 text-sm">
                  {preview.file_errors.map((e) => (
                    <li key={e} className="flex gap-2 text-coral"><OctagonX className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{e}</li>
                  ))}
                  {preview.problems.map((p, i) => (
                    <li key={i} className={cn("flex gap-2", p.level === "error" ? "text-coral" : "text-cream")}>
                      {p.level === "error" ? <OctagonX className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-saffron" aria-hidden />}
                      <span><span className="font-mono text-xs text-mist">Row {p.row}</span> {p.message}</span>
                    </li>
                  ))}
                </ul>
              </GlassCard>

              <GlassCard padding="none" aria-labelledby="rows-title">
                <h2 id="rows-title" className="px-4 pt-4 font-display text-lg font-semibold text-cream">
                  Row preview <span className="text-sm font-normal text-mist">(first {preview.rows.length} of {preview.rows_total})</span>
                </h2>
                <div className="overflow-x-auto p-2">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="text-mist">
                        <th scope="col" className="px-2 py-2">Row</th>
                        {PREVIEW_COLS.map((c) => (
                          <th scope="col" key={c} className="px-2 py-2 font-semibold uppercase tracking-wider">
                            {preview.fields.find((f) => f.field === c)?.label ?? c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.rows.map((r) => {
                        const bad = new Set(r.problems.map((p) => p.field));
                        return (
                          <tr key={r.row} className={cn("border-t border-white/5", r.problems.length > 0 && "bg-saffron/[0.06]")}>
                            <td className="px-2 py-1.5 font-mono text-mist">{r.row}</td>
                            {PREVIEW_COLS.map((c) => (
                              <td key={c} className={cn("whitespace-nowrap px-2 py-1.5 text-cream", bad.has(c) && "font-semibold text-saffron underline decoration-dotted")}
                                title={r.problems.find((p) => p.field === c)?.message}>
                                {r.values[c] || <span className="text-mist/60">(empty)</span>}
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-end gap-3">
            {!preview.can_import && <p className="text-sm text-coral">Fix the blocking errors to import.</p>}
            <Button disabled={!preview.can_import || !!busy} onClick={() => setConfirm(true)}>
              Import and validate
            </Button>
          </div>
        </>
      )}

      <Modal
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Replace student records?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(false)}>Cancel</Button>
            <Button loading={busy === "commit"} onClick={commit}>Import {preview?.rows_total} records</Button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-cream">
          This replaces all student records for <b>{me.school_code}</b> with the {preview?.rows_total} rows in{" "}
          <b>{file?.name}</b>, then runs every rule. The import and the validation are both written to the audit log.
        </p>
        <p className="mt-3 text-sm text-mist">Decisions already made on issues are kept. A fix that this file undoes will reopen.</p>
      </Modal>
    </div>
  );
}

function SummaryTile({ icon: Icon, tone, label, value, hint }: { icon: typeof FileSpreadsheet; tone: string; label: string; value: number; hint: string }) {
  return (
    <div className="glass flex items-center gap-4 p-5">
      <Icon className={cn("h-8 w-8", tone)} aria-hidden />
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-mist">{label}</p>
        <p className={cn("font-display text-2xl font-bold", tone)}>{value}</p>
        <p className="text-xs text-mist">{hint}</p>
      </div>
    </div>
  );
}
