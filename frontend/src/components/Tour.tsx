import { ArrowLeft, ArrowRight, Compass, RotateCcw, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { post, type Role } from "../lib/api";
import { useSession } from "../lib/session";
import { Button } from "./Button";
import { useToast } from "./Toast";

/**
 * Guided tour of the five-minute demo story (DEMO_SCRIPT.md). Each step signs in as the right
 * demo role and school, opens the screen, and outlines the part to look at. The tour only
 * navigates and explains: every change is still made by the person pressing the buttons.
 */
type Step = { role: Role; school?: string; path: string; target?: string; title: string; body: string };

export const TOUR: Step[] = [
  {
    role: "principal", school: "SYN-0002", path: "/app/dashboard", target: "readiness",
    title: "The principal's dashboard",
    body: "Govt UP School Hillview has 61 synthetic students. The readiness score is the share of records with no open problem. Every problem below has a rule, a plain reason and, where possible, a suggested fix.",
  },
  {
    role: "principal", school: "SYN-0002", path: "/app/upload", target: "load-sample",
    title: "Import the school's own file",
    body: "Press Load sample messy file. Rsafe maps the columns itself, lists warnings by row and masks Aadhaar to the last four digits. Nothing is saved until you press Import and validate.",
  },
  {
    role: "principal", school: "SYN-0002", path: "/app/dashboard?rule=STU-005", target: "issues",
    title: "Every flag explains itself",
    body: "Open Ananya Kumar. You see the reason, the evidence and the register's spelling as a suggestion. Open \"Why was this flagged?\" to see the rule version and the data it read. Approve fix writes to the audit log.",
  },
  {
    role: "principal", school: "SYN-0002", path: "/app/dashboard?rule=STU-002", target: "issues",
    title: "Smart fix suggestions",
    body: "Open the 31/02/2015 row. Rsafe proposes the date from the admission register and says why. Approve it, or press Reject suggestion and enter the right value yourself.",
  },
  {
    role: "principal", school: "SYN-0001", path: "/app/dashboard", target: "held",
    title: "Dropout flags wait for a person",
    body: "Both students are marked as dropouts but attended 13 days last month. Rsafe holds the flag and never applies it by itself: the principal checks with the family first.",
  },
  {
    role: "principal", school: "SYN-0002", path: "/app/export", target: "test-submit",
    title: "Test submit before you submit",
    body: "Press Test submit. Every rule runs again and you see exactly which rows would be sent, flagged, rejected or held back. Nothing is exported.",
  },
  {
    role: "mis_coordinator", path: "/app/duplicates",
    title: "The same child in two schools",
    body: "Matched by a keyed token of the Aadhaar number, never by name: 'Bhavya Rao' and 'Bhavya R.' are found to be one child, and no raw ID leaves either school.",
  },
  {
    role: "mis_coordinator", path: "/app/cluster",
    title: "The cluster at a glance",
    body: "Each school is ready, fixing or blocked. Hover a tile for its reasons; click to drill in.",
  },
  {
    role: "admin", path: "/app/audit",
    title: "A log that shows tampering",
    body: "Every action from this tour is here. Press Verify chain, then Tamper row (demo), then Verify chain again: the edited row is pinpointed.",
  },
  {
    role: "student_parent", path: "/app/my-record",
    title: "What a parent sees",
    body: "The child's record in plain words. Switch the language to हिन्दी or മലയാളം (machine translations, marked for review). The confirmation flow is a mockup: no SMS is sent.",
  },
];

type Ctx = { active: boolean; step: number; start: () => void; stop: () => void; go: (i: number) => void };

const KEY = "rsafe.tour";
function saved(): { active: boolean; step: number } | null {
  try {
    const v = JSON.parse(sessionStorage.getItem(KEY) ?? "null");
    return v && typeof v.step === "number" && v.step >= 0 && v.step < TOUR.length ? v : null;
  } catch {
    return null;
  }
}
const TourContext = createContext<Ctx | null>(null);

export function useTour() {
  const ctx = useContext(TourContext);
  if (!ctx) throw new Error("useTour must be used inside <TourProvider>");
  return ctx;
}

/** Outline around the element marked data-tour="<target>", following it on scroll and resize. */
function Highlight({ target }: { target: string }) {
  const [rect, setRect] = useState<DOMRect | null>(null);
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const el = document.querySelector(`[data-tour="${target}"]`);
      setRect(el ? el.getBoundingClientRect() : null);
      raf = window.setTimeout(tick, 250) as unknown as number;
    };
    tick();
    return () => window.clearTimeout(raf);
  }, [target]);
  if (!rect || rect.width === 0) return null;
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed z-40 rounded-[22px] ring-2 ring-saffron ring-offset-4 ring-offset-transparent transition-all duration-300 motion-safe:animate-pulse"
      style={{ left: rect.left - 4, top: rect.top - 4, width: rect.width + 8, height: rect.height + 8 }}
    />
  );
}

function TourCard() {
  const { step, go, stop } = useTour();
  const toast = useToast();
  const [resetting, setResetting] = useState(false);
  const s = TOUR[step];
  const last = step === TOUR.length - 1;

  const reset = async () => {
    setResetting(true);
    try {
      await post("/demo/reset");
      toast({ kind: "success", title: "Demo data reset", body: "Fresh synthetic data; the new audit log starts with your reset." });
      window.setTimeout(() => window.location.reload(), 600); // every screen re-reads the fresh data; the tour resumes
    } catch (e) {
      toast({ kind: "error", title: "Reset failed", body: (e as Error).message });
    } finally {
      setResetting(false);
    }
  };

  return (
    <>
      {s.target && <Highlight target={s.target} />}
      <section
        aria-label="Guided tour"
        aria-live="polite"
        className="glass fixed bottom-4 left-4 z-50 w-[min(24rem,calc(100vw-2rem))] !bg-bg-deep/90 p-5 shadow-2xl"
      >
        <div className="flex items-center gap-2">
          <Compass className="h-5 w-5 text-saffron" aria-hidden />
          <p className="text-xs font-semibold uppercase tracking-wider text-saffron">
            Guided tour · step {step + 1} of {TOUR.length}
          </p>
          <button type="button" onClick={stop} aria-label="End tour"
            className="ml-auto rounded-full p-1 text-mist hover:bg-white/10 hover:text-cream focus-visible:outline-2 focus-visible:outline-saffron">
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <h2 className="mt-2 font-display text-lg font-semibold text-cream">{s.title}</h2>
        <p className="mt-1 text-sm leading-relaxed text-mist">{s.body}</p>
        <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/10" aria-hidden>
          <div className="h-full rounded-full bg-saffron transition-all" style={{ width: `${((step + 1) / TOUR.length) * 100}%` }} />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {step === 0 && (
            <Button size="sm" variant="ghost" loading={resetting} onClick={reset} icon={<RotateCcw className="h-4 w-4" aria-hidden />}>
              Reset demo data first
            </Button>
          )}
          <div className="ml-auto flex gap-2">
            {step > 0 && (
              <Button size="sm" variant="ghost" onClick={() => go(step - 1)} icon={<ArrowLeft className="h-4 w-4" aria-hidden />}>
                Back
              </Button>
            )}
            <Button size="sm" onClick={() => (last ? stop() : go(step + 1))} iconRight={last ? undefined : <ArrowRight className="h-4 w-4" aria-hidden />}>
              {last ? "Finish" : "Next"}
            </Button>
          </div>
        </div>
      </section>
    </>
  );
}

export function TourProvider({ children }: { children: ReactNode }) {
  const { identity, signIn } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const [active, setActive] = useState(() => saved()?.active ?? false);
  const [step, setStep] = useState(() => saved()?.step ?? 0);

  useEffect(() => {
    try {
      sessionStorage.setItem(KEY, JSON.stringify({ active, step }));
    } catch {
      /* storage blocked: the tour simply does not survive a reload */
    }
  }, [active, step]);

  const go = useCallback(
    async (i: number) => {
      const s = TOUR[i];
      try {
        const needs = !identity || identity.role !== s.role || (s.school && identity.school_code !== s.school);
        if (needs) await signIn(s.role, s.school);
        setStep(i);
        setActive(true);
        // a fresh path (with a nonce) re-opens the screen even when it is already showing
        navigate(s.path, { state: { tour: Date.now() } });
      } catch (e) {
        toast({ kind: "error", title: "Tour could not continue", body: (e as Error).message });
      }
    },
    [identity, signIn, navigate, toast],
  );

  const start = useCallback(() => void go(0), [go]);
  const stop = useCallback(() => setActive(false), []);

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !document.querySelector("[role=dialog]")) setActive(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active]);

  const value = useMemo(() => ({ active, step, start, stop, go: (i: number) => void go(i) }), [active, step, start, stop, go]);
  return (
    <TourContext.Provider value={value}>
      {children}
      {active && <TourCard />}
    </TourContext.Provider>
  );
}
