import { BookUser, GraduationCap, Network, School, ShieldCheck, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { RoleCard, useToast } from "../components";
import { SYNTHETIC_LINE } from "../copy";
import type { Role } from "../lib/api";
import { HOME, useSession } from "../lib/session";

export const ROLE_CARDS: { role: Role; icon: LucideIcon; title: string; description: string; accent: "saffron" | "aqua" | "violet" | "coral" }[] = [
  { role: "principal", icon: School, title: "Principal", description: "Review issues, approve or hold, export.", accent: "saffron" },
  { role: "teacher", icon: GraduationCap, title: "Teacher", description: "See and fix records for your own classes.", accent: "aqua" },
  { role: "mis_coordinator", icon: Network, title: "MIS Coordinator", description: "Cluster view across schools.", accent: "violet" },
  { role: "student_parent", icon: BookUser, title: "Student and Parent", description: "See your record status, confirm details (consent mockup).", accent: "aqua" },
  { role: "admin", icon: ShieldCheck, title: "Admin", description: "Rules, audit log and system settings.", accent: "coral" },
];

export function RoleGrid() {
  const { signIn } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState<Role | null>(null);
  const enter = async (role: Role) => {
    if (busy) return;
    setBusy(role);
    try {
      await signIn(role);
      navigate(HOME[role]);
    } catch (e) {
      toast({ kind: "error", title: "Could not sign in", body: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
      {ROLE_CARDS.map((c) => (
        <RoleCard key={c.role} icon={c.icon} title={c.title} description={c.description} accent={c.accent} onEnter={() => enter(c.role)} />
      ))}
    </div>
  );
}

export function Enter() {
  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col justify-center px-6 py-16">
      <Link to="/" className="mb-10 font-display text-2xl font-bold text-cream focus-visible:outline-2 focus-visible:outline-saffron">
        Rsafe
      </Link>
      <h1 className="font-display text-4xl font-bold tracking-tight text-cream md:text-5xl">Who are you?</h1>
      <p className="mt-3 max-w-2xl text-mist">
        Pick a demo role. Each one sees only what that person would see; the server checks the role on every request.
      </p>
      <div className="mt-10">
        <h2 className="sr-only">Demo roles</h2>
        <RoleGrid />
      </div>
      <p className="mt-10 text-sm text-mist">{SYNTHETIC_LINE} No real students, schools or Aadhaar numbers.</p>
    </main>
  );
}
