import {
  BookOpen,
  BookUser,
  Network,
  Users,
  Download,
  GitCompareArrows,
  LayoutDashboard,
  Loader2,
  LogOut,
  ShieldCheck,
  Upload,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { Navigate, NavLink, Outlet, useNavigate } from "react-router-dom";
import { ROLE_LABEL, type Role, type SchoolOption, type SchoolSummary } from "../lib/api";
import { cn } from "../lib/cn";
import { can, HOME, useSession } from "../lib/session";
import { useApi } from "../lib/useApi";
import { useToast } from "./Toast";

type NavItem = { to: string; label: string; icon: LucideIcon };

const NAV: Record<Role, NavItem[]> = {
  principal: [
    { to: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { to: "/app/upload", label: "Upload", icon: Upload },
    { to: "/app/duplicates", label: "Duplicates", icon: GitCompareArrows },
    { to: "/app/export", label: "Export", icon: Download },
    { to: "/app/rules", label: "Rules", icon: BookOpen },
  ],
  teacher: [
    { to: "/app/classes", label: "My classes", icon: Users },
    { to: "/app/dashboard", label: "Issue list", icon: LayoutDashboard },
    { to: "/app/rules", label: "Rules", icon: BookOpen },
  ],
  mis_coordinator: [
    { to: "/app/cluster", label: "Cluster", icon: Network },
    { to: "/app/dashboard", label: "Issue list", icon: LayoutDashboard },
    { to: "/app/duplicates", label: "Duplicates", icon: GitCompareArrows },
    { to: "/app/export", label: "Export", icon: Download },
    { to: "/app/rules", label: "Rules", icon: BookOpen },
  ],
  admin: [
    { to: "/app/audit", label: "Audit log", icon: ShieldCheck },
    { to: "/app/rules", label: "Rules", icon: BookOpen },
    { to: "/app/cluster", label: "Schools", icon: Network },
    { to: "/app/dashboard", label: "All issues", icon: LayoutDashboard },
  ],
  student_parent: [{ to: "/app/my-record", label: "My record", icon: BookUser }],
};

const ROLES = Object.keys(ROLE_LABEL) as Role[];

function NavLinks({ items, compact }: { items: NavItem[]; compact?: boolean }) {
  return (
    <>
      {items.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              "flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
              "focus-visible:outline-2 focus-visible:outline-saffron",
              isActive ? "bg-saffron/15 text-saffron" : "text-mist hover:bg-white/10 hover:text-cream",
              compact && "py-2",
            )
          }
        >
          <Icon className="h-[18px] w-[18px]" aria-hidden />
          {label}
        </NavLink>
      ))}
    </>
  );
}

const selectCls =
  "h-9 rounded-full border border-white/15 bg-bg-mid/70 pl-3 pr-8 text-sm text-cream focus-visible:outline-2 focus-visible:outline-saffron disabled:opacity-60";

/** Demo role switcher: a role, plus a school for Principal and Teacher. */
function RoleSwitcher({ role, school }: { role: Role; school: string | null }) {
  const { signIn } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const schools = useApi<SchoolOption[]>("/schools");

  const switchTo = async (next: Role, code?: string) => {
    setBusy(true);
    try {
      await signIn(next, can.pickSchool(next) ? code ?? school ?? undefined : undefined);
      navigate(HOME[next]);
    } catch (err) {
      toast({ kind: "error", title: "Could not switch", body: (err as Error).message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-mist">
      <span className="hidden sm:inline">Demo as</span>
      <select aria-label="Switch demo role" value={role} disabled={busy} onChange={(e) => switchTo(e.target.value as Role)} className={selectCls}>
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {ROLE_LABEL[r]}
          </option>
        ))}
      </select>
      {can.pickSchool(role) && schools.data && (
        <select aria-label="Switch school" value={school ?? ""} disabled={busy} onChange={(e) => switchTo(role, e.target.value)} className={selectCls}>
          {schools.data.map((s) => (
            <option key={s.code} value={s.code}>
              {s.code} · {s.name}
            </option>
          ))}
        </select>
      )}
      {busy && <Loader2 className="h-4 w-4 animate-spin" aria-label="Switching" />}
    </div>
  );
}

export function AppShell() {
  const { identity, loading, signOut } = useSession();
  const navigate = useNavigate();
  const summary = useApi<{ schools: SchoolSummary[] }>(identity ? `/summary?as=${encodeURIComponent(identity.actor)}` : null);

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center text-mist">
        <Loader2 className="h-6 w-6 animate-spin" aria-label="Loading" />
      </div>
    );
  }
  if (!identity) return <Navigate to="/enter" replace />;

  const schools = summary.data?.schools ?? [];
  const place =
    identity.role === "mis_coordinator"
      ? `Cluster ${identity.cluster} · ${schools.length} schools`
      : identity.role === "admin"
        ? "All schools"
        : schools[0]
          ? `${schools[0].name} (${schools[0].school_code})`
          : identity.school_code ?? "";

  return (
    <div className="flex min-h-screen">
      <aside className="glass sticky top-4 m-4 hidden h-[calc(100vh-2rem)] w-60 shrink-0 flex-col p-4 md:flex" aria-label="Main">
        <NavLink to={HOME[identity.role]} className="mb-6 flex items-center gap-2 px-2 pt-1 focus-visible:outline-2 focus-visible:outline-saffron">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-saffron font-display text-lg font-bold text-ink">R</span>
          <span className="font-display text-xl font-bold text-cream">Rsafe</span>
        </NavLink>
        <nav className="flex flex-col gap-1" aria-label="Sections">
          <NavLinks items={NAV[identity.role]} />
        </nav>
        <div className="mt-auto border-t border-white/10 pt-4">
          <p className="px-2 text-xs text-mist">Signed in as</p>
          <p className="truncate px-2 text-sm font-medium text-cream" title={identity.actor}>
            {identity.actor}
          </p>
          <button
            type="button"
            onClick={async () => {
              await signOut();
              navigate("/enter");
            }}
            className="mt-3 flex w-full items-center gap-2 rounded-xl px-2 py-2 text-sm text-mist transition hover:bg-white/10 hover:text-cream focus-visible:outline-2 focus-visible:outline-saffron"
          >
            <LogOut className="h-4 w-4" aria-hidden /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass sticky top-4 z-30 mx-4 mt-4 flex flex-wrap items-center gap-3 !rounded-2xl px-4 py-3 md:ml-0">
          <div className="min-w-0 flex-1">
            <p className="text-xs uppercase tracking-wider text-mist">{ROLE_LABEL[identity.role]}</p>
            <p className="truncate font-display text-base font-semibold text-cream">{place}</p>
          </div>
          <span className="rounded-full bg-violet/20 px-3 py-1 text-xs font-semibold text-violet ring-1 ring-inset ring-violet/40">
            Synthetic data
          </span>
          <RoleSwitcher role={identity.role} school={identity.school_code} />
          <nav className="-mx-1 flex w-full gap-1 overflow-x-auto md:hidden" aria-label="Sections">
            <NavLinks items={NAV[identity.role]} compact />
          </nav>
        </header>
        <main id="main" className="flex-1 px-4 py-6 md:pl-0 md:pr-6">
          {/* remount on identity change so no page shows data fetched for the previous role */}
          <Outlet key={identity.actor} />
        </main>
      </div>
    </div>
  );
}
