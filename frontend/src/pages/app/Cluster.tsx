import { ArrowLeft, ArrowRight, Ban, CheckCircle2, CircleDashed, Merge, OctagonX, Wrench } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { GlassCard, ReadinessRing, SeverityBadge } from "../../components";
import { ErrorNote, Loading, PageHeader, Stat } from "../../components/ui";
import { isOpenTile, type ClusterStatus, type ClusterTile, type ClusterView, type OpenTile } from "../../lib/api";
import { cn } from "../../lib/cn";
import { can, useIdentity } from "../../lib/session";
import { useApi } from "../../lib/useApi";

const STATUS: Record<ClusterStatus, { label: string; cls: string; ring: string; Icon: typeof CheckCircle2; meaning: string }> = {
  ready: { label: "Ready", cls: "text-aqua", ring: "ring-aqua/50 bg-aqua/[0.08]", Icon: CheckCircle2, meaning: "Nothing waiting. Can be submitted." },
  fixing: { label: "Fixing", cls: "text-saffron", ring: "ring-saffron/50 bg-saffron/[0.08]", Icon: Wrench, meaning: "Only medium or low issues left." },
  blocked: { label: "Blocked", cls: "text-coral", ring: "ring-coral/50 bg-coral/[0.08]", Icon: OctagonX, meaning: "A high-severity or held issue needs a decision." },
};

function Tile({ t }: { t: ClusterTile }) {
  if (!isOpenTile(t)) {
    return (
      <div className="glass flex flex-col gap-2 p-5 opacity-70">
        <div className="flex items-center gap-2 text-mist">
          {t.status === "merged" ? <Merge className="h-5 w-5" aria-hidden /> : <Ban className="h-5 w-5" aria-hidden />}
          <span className="text-xs font-semibold uppercase tracking-wider">{t.status === "merged" ? "Merged" : "Closed"}</span>
        </div>
        <p className="font-display text-lg font-semibold text-cream">{t.name}</p>
        <p className="font-mono text-xs text-mist">{t.school_code}</p>
        <p className="text-sm text-mist">
          {t.status === "merged" ? `Merged into ${t.merged_into}. Its students should appear there with a transfer status (SYS-001).` : "No longer reports."}
        </p>
      </div>
    );
  }
  const s = STATUS[t.status];
  const blocking = t.reasons.filter((r) => r.blocking);
  return (
    <Link
      to={`/app/cluster/${t.school_code}`}
      className={cn(
        "glass group relative flex flex-col gap-3 p-5 ring-2 ring-inset transition hover:-translate-y-1",
        "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-saffron",
        s.ring,
      )}
      aria-describedby={`why-${t.school_code}`}
    >
      <div className={cn("flex items-center gap-2", s.cls)}>
        <s.Icon className="h-5 w-5" aria-hidden />
        <span className="text-xs font-bold uppercase tracking-wider">{s.label}</span>
        <span className="ml-auto font-display text-2xl font-bold text-cream">{t.readiness}%</span>
      </div>
      <div>
        <p className="font-display text-lg font-semibold text-cream">{t.name}</p>
        <p className="font-mono text-xs text-mist">{t.school_code} · {t.students} students</p>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10" aria-hidden>
        <div className={cn("h-full rounded-full", t.status === "ready" ? "bg-aqua" : t.status === "fixing" ? "bg-saffron" : "bg-coral")} style={{ width: `${t.readiness}%` }} />
      </div>
      <p className="text-sm text-mist">
        {t.active} need action{t.held ? `, ${t.held} held` : ""} · {t.decided} fixed by staff
      </p>
      {/* Reason on hover or keyboard focus; also read out via aria-describedby */}
      <div
        id={`why-${t.school_code}`}
        role="tooltip"
        className="pointer-events-none absolute inset-x-3 top-full z-20 mt-2 rounded-2xl border border-white/15 bg-bg-mid/95 p-4 text-sm opacity-0 shadow-2xl backdrop-blur transition group-hover:opacity-100 group-focus-visible:opacity-100"
      >
        <p className="mb-1 font-semibold text-cream">{t.status === "blocked" ? "Blocking reasons" : t.status === "fixing" ? "Still open" : "All clear"}</p>
        {(blocking.length ? blocking : t.reasons).slice(0, 4).map((r) => (
          <p key={r.rule_id} className="text-mist">
            <span className="font-mono text-xs text-cream">{r.rule_id}</span> {r.title} ({r.count}
            {r.held ? `, ${r.held} held` : ""})
          </p>
        ))}
        {t.reasons.length === 0 && <p className="text-mist">No open issues.</p>}
      </div>
    </Link>
  );
}

export function Cluster() {
  const view = useApi<ClusterView>("/cluster");
  if (view.loading && !view.data) return <Loading label="Loading cluster" />;
  if (view.error) return <ErrorNote error={view.error} onRetry={view.reload} />;
  const v = view.data!;
  const open = v.schools.filter(isOpenTile);
  return (
    <div>
      <PageHeader title={`Cluster ${v.cluster}`} subtitle={`${open.length} reporting schools, ${v.students} students. Hover or focus a school to see why; click to drill in.`} />
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        {(["ready", "fixing", "blocked"] as const).map((k) => (
          <div key={k} className="glass flex items-center gap-4 p-5">
            {(() => {
              const S = STATUS[k];
              return <S.Icon className={cn("h-8 w-8", S.cls)} aria-hidden />;
            })()}
            <div>
              <p className={cn("font-display text-3xl font-bold", STATUS[k].cls)}>{v.counts[k] ?? 0}</p>
              <p className="text-sm text-cream">{STATUS[k].label}</p>
              <p className="text-xs text-mist">{STATUS[k].meaning}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="grid gap-5 pb-24 sm:grid-cols-2 xl:grid-cols-4">
        {v.schools.map((t) => (
          <Tile key={t.school_code} t={t} />
        ))}
      </div>
    </div>
  );
}

export function ClusterSchool() {
  const { code } = useParams();
  const me = useIdentity();
  const view = useApi<ClusterView>("/cluster");
  if (view.loading && !view.data) return <Loading />;
  if (view.error) return <ErrorNote error={view.error} onRetry={view.reload} />;
  const t = view.data!.schools.find((x) => x.school_code === code);
  if (!t || !isOpenTile(t)) {
    return (
      <div>
        <Link to="/app/cluster" className="text-saffron hover:underline">← Back to cluster</Link>
        <p className="mt-4 text-mist">That school is not reporting in your cluster.</p>
      </div>
    );
  }
  const tile = t as OpenTile;
  const s = STATUS[tile.status];
  return (
    <div>
      <Link to="/app/cluster" className="mb-4 inline-flex items-center gap-1 text-sm text-saffron hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Cluster {view.data!.cluster}
      </Link>
      <PageHeader
        title={tile.name}
        subtitle={
          <span className={cn("inline-flex items-center gap-1.5 font-semibold", s.cls)}>
            <s.Icon className="h-4 w-4" aria-hidden /> {s.label}: <span className="font-normal text-mist">{s.meaning}</span>
          </span>
        }
        actions={
          <>
            <Link to={`/app/dashboard?school=${tile.school_code}`} className="inline-flex h-11 items-center gap-2 rounded-full bg-saffron px-5 font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-[3px] focus-visible:outline-saffron">
              Open issue list <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
            {can.export(me.role) && (
              <Link to={`/app/export?school=${tile.school_code}`} className="glass inline-flex h-11 items-center !rounded-full px-5 font-semibold text-cream hover:bg-white/15">
                Export
              </Link>
            )}
          </>
        }
      />
      <div className="grid gap-4 lg:grid-cols-[auto_1fr]">
        <GlassCard className="flex items-center justify-center">
          <ReadinessRing value={tile.readiness} />
        </GlassCard>
        <div className="grid content-start gap-4 sm:grid-cols-4">
          <Stat label="Students" value={tile.students} />
          <Stat label="Need action" value={tile.active - tile.held} tone={tile.active - tile.held ? "saffron" : "aqua"} />
          <Stat label="Held" value={tile.held} tone={tile.held ? "coral" : "aqua"} />
          <Stat label="Fixed by staff" value={tile.decided} tone="aqua" hint={`${tile.resolved} cleared on re-check`} />
        </div>
      </div>
      <GlassCard className="mt-4" padding="none">
        <h2 className="border-b border-white/10 p-4 font-display text-lg font-semibold text-cream">What is open, by rule</h2>
        {tile.reasons.length === 0 ? (
          <p className="flex items-center gap-2 p-4 text-aqua"><CircleDashed className="h-4 w-4" aria-hidden /> Nothing is open.</p>
        ) : (
          <ul>
            {tile.reasons.map((r) => (
              <li key={r.rule_id} className="border-b border-white/5 last:border-0">
                <Link
                  to={`/app/dashboard?school=${tile.school_code}&rule=${r.rule_id}`}
                  className="flex flex-wrap items-center gap-3 px-4 py-3 transition hover:bg-white/[0.06] focus-visible:outline-2 focus-visible:outline-saffron"
                >
                  <SeverityBadge severity={r.severity} />
                  <span className="font-mono text-xs text-cream">{r.rule_id}</span>
                  <span className="flex-1 text-sm text-cream">{r.title}</span>
                  {r.blocking && <span className="rounded-full bg-coral/15 px-2 py-0.5 text-xs font-semibold text-coral">Blocking</span>}
                  <span className="font-display text-lg font-semibold text-cream">{r.count}</span>
                  {r.held > 0 && <span className="text-xs text-coral">{r.held} held</span>}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </GlassCard>
    </div>
  );
}
