import { AlertTriangle, CheckCircle2, Download, FileText } from "lucide-react";
import { useState } from "react";
import { GlassCard, ReadinessRing, useToast } from "../../components";
import { ErrorNote, Loading, PageHeader, Select, Stat } from "../../components/ui";
import { qs, type SchoolSummary } from "../../lib/api";
import { cn } from "../../lib/cn";
import { useIdentity } from "../../lib/session";
import { useApi } from "../../lib/useApi";

const linkBtn =
  "inline-flex h-11 items-center gap-2 rounded-full px-5 text-[15px] font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-[3px] focus-visible:outline-saffron";

export function Export() {
  const me = useIdentity();
  const toast = useToast();
  const summary = useApi<{ schools: SchoolSummary[] }>("/summary");
  const schools = summary.data?.schools ?? [];
  const [picked, setPicked] = useState("");
  const school = schools.find((s) => s.school_code === picked) ?? schools[0];
  const q = qs({ school_code: school?.school_code });

  if (summary.loading && !summary.data) return <Loading />;
  if (summary.error) return <ErrorNote error={summary.error} onRetry={summary.reload} />;
  if (!school) return <p className="text-mist">No school to export.</p>;

  const ready = school.active === 0;
  return (
    <div>
      <PageHeader
        title="Export"
        subtitle="Download the checked file and a one-page readiness report. Rsafe never submits anything itself."
        actions={
          schools.length > 1 && (
            <Select label="School" value={school.school_code} onChange={(e) => setPicked(e.target.value)}>
              {schools.map((s) => (
                <option key={s.school_code} value={s.school_code}>{s.school_code} · {s.name}</option>
              ))}
            </Select>
          )
        }
      />

      <div className="grid gap-4 lg:grid-cols-[auto_1fr]">
        <GlassCard className="flex flex-col items-center gap-2">
          <ReadinessRing value={school.readiness} />
          <p className="text-sm text-mist">{school.name}</p>
        </GlassCard>
        <div className="grid content-start gap-4 sm:grid-cols-3">
          <Stat label="Student records" value={school.students} />
          <Stat label="Need action" value={school.active - school.held} tone={school.active - school.held ? "saffron" : "aqua"} />
          <Stat label="Held" value={school.held} tone={school.held ? "coral" : "aqua"} />
          <div className={cn("glass flex items-start gap-3 p-5 sm:col-span-3", ready ? "!bg-aqua/[0.07]" : "!bg-saffron/[0.07]")}>
            {ready ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-aqua" aria-hidden /> : <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-saffron" aria-hidden />}
            <p className="text-sm text-cream">
              {ready
                ? "Every issue has a decision. The file is ready to upload to UDISE+ by hand."
                : `${school.active} issue(s) still need a decision. You can export now; those students are marked in the rsafe_status column so nothing is hidden.`}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <GlassCard>
          <Download className="h-7 w-7 text-saffron" aria-hidden />
          <h2 className="mt-3 font-display text-lg font-semibold text-cream">Cleaned student CSV</h2>
          <p className="mt-1 text-sm text-mist">
            Current values after every approved fix and edit, with a status per student. Aadhaar is masked to the last four digits;
            re-attach the full number from the school's own system when submitting.
          </p>
          <a
            href={`/api/export/csv${q}`}
            download
            onClick={() => toast({ kind: "info", title: "Export logged", body: "The download is recorded in the audit log." })}
            className={cn(linkBtn, "mt-4 bg-saffron text-ink hover:brightness-105")}
          >
            <Download className="h-4 w-4" aria-hidden /> Download CSV
          </a>
        </GlassCard>
        <GlassCard>
          <FileText className="h-7 w-7 text-violet" aria-hidden />
          <h2 className="mt-3 font-display text-lg font-semibold text-cream">Submission readiness report</h2>
          <p className="mt-1 text-sm text-mist">
            One page: issues found, fixed, held, who approved each change, the rule versions used and whether the audit chain is intact.
            Print it or save as PDF from the browser.
          </p>
          <a href={`/api/export/report${q}`} target="_blank" rel="noopener" className={cn(linkBtn, "glass mt-4 !rounded-full text-cream hover:bg-white/15")}>
            <FileText className="h-4 w-4" aria-hidden /> Open report <span className="sr-only">(opens in a new tab)</span>
          </a>
        </GlassCard>
      </div>
      {me.role === "mis_coordinator" && <p className="mt-4 text-xs text-mist">Exports are recorded in the audit log under your name.</p>}
    </div>
  );
}
