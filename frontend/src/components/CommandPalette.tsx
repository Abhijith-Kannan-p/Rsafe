import { BookOpen, Compass, CornerDownLeft, LayoutDashboard, Search, UserRound, type LucideIcon } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { api, type Role, type Rule, type SearchHit } from "../lib/api";
import { cn } from "../lib/cn";
import { useApi } from "../lib/useApi";
import { useTour } from "./Tour";

export type PaletteScreen = { to: string; label: string; icon: LucideIcon };
type Item = { id: string; group: string; label: string; hint?: string; icon: LucideIcon; run: () => void };

const STAFF: Role[] = ["principal", "teacher", "mis_coordinator", "admin"];

/** Ctrl+K / Cmd+K: jump to any screen, rule or (for staff) student record the role may see. */
export function CommandPalette({ open, onClose, role, screens }: { open: boolean; onClose: () => void; role: Role; screens: PaletteScreen[] }) {
  const navigate = useNavigate();
  const tour = useTour();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();
  const rules = useApi<Rule[]>(open ? "/rules" : null);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setHits([]);
    setActive(0);
    const t = window.setTimeout(() => input.current?.focus(), 10);
    return () => window.clearTimeout(t);
  }, [open]);

  // student search, debounced, only for staff roles (the server checks too)
  useEffect(() => {
    if (!open || !STAFF.includes(role) || q.trim().length < 2) {
      setHits([]);
      return;
    }
    let live = true;
    const t = window.setTimeout(() => {
      api<SearchHit[]>(`/search?q=${encodeURIComponent(q.trim())}`).then((h) => live && setHits(h)).catch(() => live && setHits([]));
    }, 180);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
  }, [q, open, role]);

  const items = useMemo<Item[]>(() => {
    const needle = q.trim().toLowerCase();
    const match = (...xs: (string | undefined)[]) => !needle || xs.some((x) => x?.toLowerCase().includes(needle));
    const go = (to: string) => () => {
      onClose();
      navigate(to);
    };
    const out: Item[] = [];
    for (const s of screens) if (match(s.label, "screen", "go to")) out.push({ id: `s:${s.to}`, group: "Screens", label: s.label, icon: s.icon, run: go(s.to) });
    if (match("guided tour", "demo", "help"))
      out.push({ id: "tour", group: "Screens", label: "Start the guided tour", icon: Compass, run: () => { onClose(); tour.start(); } });
    for (const r of rules.data ?? []) {
      if (!match(r.id, r.title, r.addresses ?? "")) continue;
      const to = STAFF.includes(role) && role !== "admin" ? `/app/dashboard?rule=${r.id}&status=all` : `/app/rules?rule=${r.id}`;
      out.push({ id: `r:${r.id}`, group: "Rules", label: `${r.id} · ${r.title}`, hint: STAFF.includes(role) && role !== "admin" ? "issues" : "rule", icon: BookOpen, run: go(to) });
    }
    for (const h of hits)
      out.push({
        id: `h:${h.student_ref}`, group: "Students", label: `${h.name || "(no name)"} · ${h.student_ref}`,
        hint: h.issue_id ? (h.active ? `${h.active} open` : "no open issues") : "no issues", icon: UserRound,
        run: go(h.issue_id ? `/app/dashboard?status=all&issue=${h.issue_id}` : `/app/dashboard?status=all`),
      });
    return out.slice(0, 30);
  }, [q, screens, rules.data, hits, role, navigate, onClose, tour]);

  useEffect(() => setActive((a) => Math.min(a, Math.max(0, items.length - 1))), [items.length]);

  if (!open) return null;
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(items.length - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); items[active]?.run(); }
    else if (e.key === "Escape") { e.preventDefault(); onClose(); }
  };
  let lastGroup = "";

  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-bg-deep/60 px-4 pt-[12vh] backdrop-blur-sm" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Jump to a screen, rule or record" onMouseDown={(e) => e.stopPropagation()}
        className="glass w-full max-w-xl overflow-hidden !bg-bg-deep/95 p-0 shadow-2xl">
        <div className="flex items-center gap-3 border-b border-white/10 px-4">
          <Search className="h-5 w-5 text-mist" aria-hidden />
          <input
            ref={input} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey}
            role="combobox" aria-expanded="true" aria-controls={listId} aria-autocomplete="list"
            aria-activedescendant={items[active] ? `${listId}-${active}` : undefined}
            placeholder={STAFF.includes(role) ? "Screens, rules (STU-002), students by name or ID" : "Screens and rules"}
            aria-label="Search screens, rules and records"
            className="h-14 flex-1 bg-transparent text-base text-cream placeholder:text-mist/70 focus:outline-none"
          />
          <kbd className="rounded-md border border-white/15 px-1.5 py-0.5 text-xs text-mist">Esc</kbd>
        </div>
        <ul id={listId} role="listbox" aria-label="Results" className="max-h-[50vh] overflow-y-auto p-2">
          {items.length === 0 && <li className="px-3 py-6 text-center text-sm text-mist">Nothing matches.</li>}
          {items.map((it, i) => {
            const header = it.group !== lastGroup ? it.group : null;
            lastGroup = it.group;
            const Icon = it.icon;
            return (
              <li key={it.id} role="presentation">
                {header && <p className="px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-wider text-mist" aria-hidden>{header}</p>}
                <div
                  id={`${listId}-${i}`} role="option" aria-selected={i === active}
                  onMouseEnter={() => setActive(i)} onClick={it.run}
                  className={cn("flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-sm", i === active ? "bg-saffron/15 text-saffron" : "text-cream")}
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden />
                  <span className="flex-1 truncate">{it.label}</span>
                  {it.hint && <span className="text-xs text-mist">{it.hint}</span>}
                  {i === active && <CornerDownLeft className="h-4 w-4" aria-hidden />}
                </div>
              </li>
            );
          })}
        </ul>
        <p className="flex items-center gap-3 border-t border-white/10 px-4 py-2 text-xs text-mist">
          <LayoutDashboard className="h-3.5 w-3.5" aria-hidden /> ↑ ↓ to move · Enter to open · Ctrl+K anywhere
        </p>
      </div>
    </div>,
    document.body,
  );
}
