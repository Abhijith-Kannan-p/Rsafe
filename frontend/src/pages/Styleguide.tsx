import {
  ArrowRight,
  BookUser,
  CheckCircle2,
  ChevronDown,
  GraduationCap,
  LayoutGrid,
  Play,
  School,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Button,
  DataTable,
  GlassCard,
  Modal,
  ReadinessRing,
  RoleCard,
  SeverityBadge,
  SidePanel,
  StatusPill,
  useToast,
  type Column,
  type Severity,
  type Status,
} from "../components";
import { api, type Health } from "../lib/api";

const SWATCHES = [
  ["bg-deep", "#0A1230", "bg-bg-deep"],
  ["bg-mid", "#122052", "bg-bg-mid"],
  ["cream", "#F7F0E1", "bg-cream"],
  ["sand", "#E9DCC0", "bg-sand"],
  ["saffron", "#FFB43B", "bg-saffron"],
  ["aqua", "#2DE2C8", "bg-aqua"],
  ["coral", "#FF6B5B", "bg-coral"],
  ["violet", "#8B7CFF", "bg-violet"],
] as const;

type DemoIssue = { id: number; rule: string; severity: Severity; record: string; status: Status };

// Illustrative rows for the styleguide only (synthetic).
const DEMO_ROWS: DemoIssue[] = [
  { id: 1, rule: "STU-002", severity: "high", record: "SYN-0001-S0014", status: "open" },
  { id: 2, rule: "STU-005", severity: "medium", record: "SYN-0002-S0031", status: "edited" },
  { id: 3, rule: "STU-008", severity: "high", record: "SYN-0003-S0007", status: "held" },
  { id: 4, rule: "FAC-001", severity: "low", record: "SYN-0002-F-toilet_girls", status: "approved" },
];

const SEV_RANK: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

const COLUMNS: Column<DemoIssue>[] = [
  { key: "rule", header: "Rule", sortValue: (r) => r.rule, render: (r) => <span className="font-mono">{r.rule}</span> },
  { key: "severity", header: "Severity", sortValue: (r) => SEV_RANK[r.severity], render: (r) => <SeverityBadge severity={r.severity} /> },
  { key: "record", header: "Record", render: (r) => <span className="font-mono text-mist">{r.record}</span> },
  { key: "status", header: "Status", sortValue: (r) => r.status, render: (r) => <StatusPill status={r.status} /> },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold text-sand">{title}</h2>
      {children}
    </section>
  );
}

export function Styleguide() {
  const toast = useToast();
  const [modal, setModal] = useState(false);
  const [panel, setPanel] = useState(false);
  const [score, setScore] = useState(74);
  const [health, setHealth] = useState<Health | "down" | null>(null);

  useEffect(() => {
    api<Health>("/health").then(setHealth).catch(() => setHealth("down"));
  }, []);

  return (
    <main className="mx-auto max-w-6xl space-y-12 px-6 py-12">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link to="/" className="text-sm text-mist hover:text-cream">
            ← Rsafe
          </Link>
          <h1 className="mt-2 text-4xl font-bold sm:text-5xl">Design system</h1>
          <p className="mt-2 text-mist">Tokens and shared components. Example rows are synthetic.</p>
        </div>
        <div className="glass flex items-center gap-2 !rounded-full px-4 py-2 text-sm" role="status">
          API:{" "}
          {health === null ? (
            <span className="text-mist">checking…</span>
          ) : health === "down" ? (
            <StatusPill status="blocked" label="offline (start the backend)" />
          ) : (
            <StatusPill status="ready" label={`ok · v${health.version}`} />
          )}
        </div>
      </header>

      <Section title="Colour tokens">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {SWATCHES.map(([name, hex, cls]) => (
            <GlassCard key={name} padding="sm" className="flex items-center gap-3">
              <span className={`h-10 w-10 shrink-0 rounded-xl ring-1 ring-white/20 ${cls}`} aria-hidden />
              <div>
                <div className="font-mono text-sm">--{name}</div>
                <div className="font-mono text-xs text-mist">{hex}</div>
              </div>
            </GlassCard>
          ))}
        </div>
      </Section>

      <Section title="Typography">
        <GlassCard className="space-y-2">
          <p className="font-display text-5xl font-bold">Sora display</p>
          <p className="font-display text-2xl font-semibold text-sand">Every record, right before it counts.</p>
          <p className="max-w-2xl text-mist">
            Inter body text. Rsafe explains each problem in plain language, suggests a fix, and never changes a
            record without a person approving it.
          </p>
        </GlassCard>
      </Section>

      <Section title="Glass surfaces">
        <div className="grid gap-4 md:grid-cols-2">
          <GlassCard>
            <h3 className="font-semibold">Dark glass</h3>
            <p className="mt-1 text-sm text-mist">rgba(255,255,255,0.08), blur 18px, saturate 140%, 4% noise.</p>
          </GlassCard>
          <GlassCard tone="light">
            <h3 className="font-semibold">Light glass</h3>
            <p className="mt-1 text-sm text-ink/75">rgba(247,240,225,0.65) for cream cards with ink text.</p>
          </GlassCard>
        </div>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button icon={<Play className="h-4 w-4" aria-hidden />}>Run validation</Button>
          <Button variant="ghost" iconRight={<ChevronDown className="h-4 w-4 animate-bounce" aria-hidden />}>
            Scroll down
          </Button>
          <Button variant="success" icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}>
            Approve fix
          </Button>
          <Button variant="danger">Hold</Button>
          <Button loading>Saving</Button>
          <Button size="sm" variant="ghost">
            Small ghost
          </Button>
          <Button size="lg" iconRight={<ArrowRight className="h-5 w-5" aria-hidden />}>
            Enter Rsafe
          </Button>
        </div>
      </Section>

      <Section title="Badges and pills">
        <div className="flex flex-wrap items-center gap-3">
          <SeverityBadge severity="high" />
          <SeverityBadge severity="medium" />
          <SeverityBadge severity="low" />
          <span className="mx-2 h-5 w-px bg-white/20" aria-hidden />
          {(["ready", "fixing", "blocked", "open", "held", "approved", "edited", "verified"] as Status[]).map((s) => (
            <StatusPill key={s} status={s} />
          ))}
        </div>
      </Section>

      <Section title="Readiness ring">
        <GlassCard className="flex flex-wrap items-center gap-10">
          <ReadinessRing value={score} />
          <ReadinessRing value={42} size={120} stroke={10} label="Blocked" />
          <ReadinessRing value={96} size={120} stroke={10} label="Ready" />
          <div className="space-y-3">
            <label htmlFor="score" className="block text-sm text-mist">
              Score: {score}
            </label>
            <input
              id="score"
              type="range"
              min={0}
              max={100}
              value={score}
              onChange={(e) => setScore(Number(e.target.value))}
              className="w-56 accent-saffron"
            />
          </div>
        </GlassCard>
      </Section>

      <Section title="Data table">
        <GlassCard padding="sm">
          <DataTable
            caption="Example issues"
            columns={COLUMNS}
            rows={DEMO_ROWS}
            rowKey={(r) => r.id}
            onRowClick={() => setPanel(true)}
          />
        </GlassCard>
        <GlassCard padding="sm">
          <DataTable caption="Empty example" columns={COLUMNS} rows={[]} rowKey={(r) => r.id} empty="No issues. This school is ready." />
        </GlassCard>
      </Section>

      <Section title="Overlays and toasts">
        <div className="flex flex-wrap gap-3">
          <Button variant="ghost" onClick={() => setModal(true)}>
            Open modal
          </Button>
          <Button variant="ghost" onClick={() => setPanel(true)}>
            Open side panel
          </Button>
          <Button variant="ghost" onClick={() => toast({ kind: "success", title: "Fix approved", body: "Written to the audit log." })}>
            Success toast
          </Button>
          <Button variant="ghost" onClick={() => toast({ kind: "error", title: "Chain broken at row 12", body: "Hash does not match the previous row." })}>
            Error toast
          </Button>
          <Button variant="ghost" onClick={() => toast({ kind: "info", title: "Dropout flag held", body: "Waiting for principal review." })}>
            Info toast
          </Button>
        </div>
      </Section>

      <Section title="Role cards">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <RoleCard icon={School} title="Principal" description="Review issues, approve or hold, export." onEnter={() => toast({ kind: "info", title: "Style guide only", body: "Use /enter to sign in as a role." })} />
          <RoleCard icon={GraduationCap} accent="aqua" title="Teacher" description="See and fix records for your own classes." onEnter={() => toast({ kind: "info", title: "Style guide only", body: "Use /enter to sign in as a role." })} />
          <RoleCard icon={LayoutGrid} accent="violet" title="MIS Coordinator" description="Cluster view across schools." onEnter={() => toast({ kind: "info", title: "Style guide only", body: "Use /enter to sign in as a role." })} />
          <RoleCard icon={BookUser} accent="aqua" title="Student and Parent" description="See your record status, confirm details (consent mockup)." onEnter={() => toast({ kind: "info", title: "Style guide only", body: "Use /enter to sign in as a role." })} />
          <RoleCard icon={ShieldCheck} accent="coral" title="Admin" description="Rules, audit log and system settings." onEnter={() => toast({ kind: "info", title: "Style guide only", body: "Use /enter to sign in as a role." })} />
        </div>
      </Section>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title="Confirm action"
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(false)}>
              Cancel
            </Button>
            <Button onClick={() => setModal(false)}>Confirm</Button>
          </>
        }
      >
        <p className="text-mist">Every correction needs a person to approve it, and each approval is written to the audit log.</p>
      </Modal>

      <SidePanel
        open={panel}
        onClose={() => setPanel(false)}
        title={
          <span className="flex items-center gap-2">
            <span className="font-mono">STU-002</span> <SeverityBadge severity="high" />
          </span>
        }
        footer={
          <>
            <Button variant="danger" onClick={() => setPanel(false)}>
              Hold
            </Button>
            <Button variant="ghost" onClick={() => setPanel(false)}>
              Edit
            </Button>
            <Button variant="success" onClick={() => setPanel(false)}>
              Approve fix
            </Button>
          </>
        }
      >
        <p className="text-sand">Date of birth cannot be read.</p>
        <p className="mt-2 text-sm text-mist">Example panel. The real issue detail opens from the dashboard.</p>
      </SidePanel>
    </main>
  );
}
