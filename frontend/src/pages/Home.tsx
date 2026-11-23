import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, ChevronDown, ClipboardCheck, FileUp, ImageOff, Lock, ScanSearch, Send, UserCheck } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components";
import { EVENT, MOTTO, SHOWCASE, SYNTHETIC_LINE, TEAM } from "../copy";
import { cn } from "../lib/cn";
import { RoleGrid } from "./Enter";

const EASE = [0.22, 1, 0.36, 1] as const;

/** Which screenshots exist. The script writes the manifest, so missing files never cause a 404. */
type Shots = { files: Set<string>; webp: Set<string> };

function useShots(): Shots {
  const [shots, setShots] = useState<Shots>({ files: new Set(), webp: new Set() });
  useEffect(() => {
    let live = true;
    fetch("/shots/manifest.json", { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : {}))
      .then((m: { files?: string[]; webp?: string[] }) => {
        if (live) setShots({ files: new Set(m.files ?? []), webp: new Set(m.webp ?? []) });
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  return shots;
}

function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.8, delay, ease: EASE }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

type FrameProps = { file: string; path: string; title: string; present: boolean; webp: boolean };

function BrowserFrame({ file, path, title, present, webp }: FrameProps) {
  return (
    <div className="glass overflow-hidden !rounded-2xl p-0">
      <div className="flex items-center gap-2 border-b border-white/10 bg-white/[0.04] px-4 py-2.5">
        <span className="h-3 w-3 rounded-full bg-coral/80" aria-hidden />
        <span className="h-3 w-3 rounded-full bg-saffron/80" aria-hidden />
        <span className="h-3 w-3 rounded-full bg-aqua/80" aria-hidden />
        <span className="ml-3 min-w-0 flex-1 truncate rounded-full bg-bg-deep/60 px-3 py-1 font-mono text-xs text-mist">
          rsafe.local{path}
        </span>
      </div>
      {present ? (
        <picture>
          {webp && <source type="image/webp" srcSet={`/shots/${file.replace(/\.png$/, ".webp")}`} />}
          <img
            src={`/shots/${file}`}
            alt={`Screenshot: ${title}`}
            width={1440}
            height={900}
            loading="lazy"
            decoding="async"
            className="block aspect-[16/10] w-full object-cover object-top"
          />
        </picture>
      ) : (
        <div className="grid aspect-[16/10] place-items-center bg-[repeating-linear-gradient(135deg,rgba(255,255,255,0.03)_0_14px,transparent_14px_28px)]">
          <div className="text-center text-mist">
            <ImageOff className="mx-auto h-8 w-8" aria-hidden />
            <p className="mt-2 text-sm">Screenshot not generated yet</p>
            <p className="font-mono text-xs">npm run screenshots</p>
          </div>
        </div>
      )}
    </div>
  );
}

function Hero() {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const scrollDown = () => document.getElementById("showcase")?.scrollIntoView({ behavior: reduce ? "auto" : "smooth" });

  return (
    <section className="relative grid min-h-[100svh] place-items-center px-6 text-center" aria-labelledby="hero-title">
      <div>
        <motion.h1
          id="hero-title"
          initial={reduce ? false : { opacity: 0, y: 24, filter: "blur(12px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 1.6, ease: EASE }}
          className="font-display text-7xl font-bold tracking-tight text-cream sm:text-8xl md:text-9xl"
        >
          Rsafe
        </motion.h1>
        <motion.p
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2, duration: 0.9 }}
          className="mt-5 text-xl text-sand sm:text-2xl"
        >
          {MOTTO}
        </motion.p>
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.9, duration: 0.6 }}
          className="mt-10 flex flex-col items-center gap-5"
        >
          <div className="flex flex-wrap justify-center gap-3">
            <Button size="lg" iconRight={<ArrowRight className="h-5 w-5" aria-hidden />} onClick={() => navigate("/enter")}>
              Enter Rsafe
            </Button>
            <Button
              size="lg"
              variant="ghost"
              onClick={scrollDown}
              iconRight={
                <motion.span
                  animate={reduce ? undefined : { y: [0, 5, 0] }}
                  transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
                  className="inline-flex"
                >
                  <ChevronDown className="h-5 w-5" aria-hidden />
                </motion.span>
              }
            >
              Scroll down
            </Button>
          </div>
          <p className="text-sm text-mist">{SYNTHETIC_LINE}</p>
        </motion.div>
      </div>
    </section>
  );
}

function SectionHead({ id, kicker, title, children }: { id: string; kicker: string; title: string; children?: ReactNode }) {
  return (
    <Reveal className="mb-12 max-w-3xl">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-saffron">{kicker}</p>
      <h2 id={id} className="mt-2 font-display text-4xl font-bold tracking-tight text-cream md:text-5xl">
        {title}
      </h2>
      {children && <p className="mt-4 text-lg text-mist">{children}</p>}
    </Reveal>
  );
}

function Showcase() {
  const shots = useShots();
  return (
    <section id="showcase" className="mx-auto max-w-7xl scroll-mt-8 px-6 py-24" aria-labelledby="showcase-title">
      <SectionHead id="showcase-title" kicker="Seven steps" title="See it catch problems">
        Real screens from the prototype, captured on synthetic data by the screenshot script.
      </SectionHead>
      <ol className="grid gap-24">
        {SHOWCASE.map((s, i) => (
          <li key={s.file} className="grid items-center gap-8 lg:grid-cols-12">
            <Reveal className={cn("lg:col-span-8", i % 2 === 1 && "lg:order-2")}>
              <BrowserFrame file={s.file} path={s.path} title={s.title} present={shots.files.has(s.file)} webp={shots.webp.has(s.file)} />
            </Reveal>
            <Reveal className={cn("lg:col-span-4", i % 2 === 1 && "lg:order-1")} delay={0.15}>
              <span className="font-display text-5xl font-bold text-saffron/40" aria-hidden>
                {String(i + 1).padStart(2, "0")}
              </span>
              <h3 className="mt-2 font-display text-2xl font-semibold text-cream">{s.title}</h3>
              <p className="mt-3 leading-relaxed text-mist">{s.caption}</p>
            </Reveal>
          </li>
        ))}
      </ol>
    </section>
  );
}

const STEPS = [
  { icon: FileUp, title: "Import", body: "The school loads its own file. Aadhaar is turned into keyed tokens on arrival; only the last 4 digits are kept." },
  { icon: ScanSearch, title: "Check", body: "Versioned YAML rules run on every record and explain each problem in plain language." },
  { icon: UserCheck, title: "Review", body: "A person approves, edits or holds each flag. Every decision is written to the audit log." },
  { icon: Send, title: "Submit", body: "Export a clean file and a readiness report. A person uploads it to UDISE+; Rsafe never submits." },
];

function HowItWorks() {
  return (
    <section className="mx-auto max-w-7xl px-6 py-24" aria-labelledby="how-title">
      <SectionHead id="how-title" kicker="Four steps" title="How it works" />
      <Reveal>
        <ol className="grid gap-4 md:grid-cols-[1fr_auto_1fr_1fr_1fr]">
          <li className="flex flex-col rounded-[24px] border-2 border-dashed border-saffron/60 bg-saffron/[0.06] p-2">
            <p className="flex items-center gap-1.5 px-3 pb-2 pt-1 text-xs font-semibold uppercase tracking-wider text-saffron">
              <Lock className="h-3.5 w-3.5" aria-hidden /> Inside the school
            </p>
            <Step n={1} {...STEPS[0]} className="flex-1" />
          </li>
          <li aria-label="Privacy boundary" className="flex items-center justify-center md:flex-col">
            <div className="h-px w-12 bg-saffron md:h-12 md:w-px" aria-hidden />
            <p className="mx-3 rounded-full bg-saffron px-4 py-1.5 text-center text-sm font-bold text-ink md:my-3 md:mx-0 md:max-w-[9rem]">
              Raw IDs stop at the school
            </p>
            <div className="h-px w-12 bg-saffron md:h-12 md:w-px" aria-hidden />
          </li>
          {STEPS.slice(1).map((s, i) => (
            <li key={s.title} className="pt-0 md:pt-9">
              <Step n={i + 2} {...s} />
            </li>
          ))}
        </ol>
        <p className="mt-6 flex items-start gap-2 text-sm text-mist">
          <ClipboardCheck className="mt-0.5 h-4 w-4 shrink-0 text-aqua" aria-hidden />
          Past the boundary only keyed tokens and last-4 digits travel, so cross-school duplicate checks work without any raw ID leaving the school.
        </p>
      </Reveal>
    </section>
  );
}

function Step({ n, icon: Icon, title, body, className = "h-full" }: { n: number; icon: typeof FileUp; title: string; body: string; className?: string }) {
  return (
    <div className={cn("glass p-5", className)}>
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-white/10 text-saffron">
          <Icon className="h-5 w-5" aria-hidden />
        </span>
        <h3 className="font-display text-lg font-semibold text-cream">
          <span className="text-mist">{n}.</span> {title}
        </h3>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-mist">{body}</p>
    </div>
  );
}

function Roles() {
  return (
    <section className="mx-auto max-w-7xl px-6 py-24" aria-labelledby="roles-title">
      <SectionHead id="roles-title" kicker="Pick a demo role" title="Who are you?">
        Each role sees only what that person would see. The server checks the role on every request.
      </SectionHead>
      <Reveal>
        <RoleGrid />
      </Reveal>
    </section>
  );
}

function Footer() {
  return (
    <footer className="mx-auto max-w-7xl px-6 pb-10 pt-6">
      <div className="glass flex flex-col gap-3 p-6 text-sm text-mist md:flex-row md:items-center md:justify-between">
        <p>
          <span className="font-display text-lg font-bold text-cream">Rsafe</span>
          <span className="mx-2" aria-hidden>·</span>
          Team <span className="font-semibold text-cream">{TEAM}</span>
          <span className="mx-2" aria-hidden>·</span>
          {EVENT}
        </p>
        <p className="max-w-xl md:text-right">
          {SYNTHETIC_LINE} No real students, schools or Aadhaar numbers. No calls to UIDAI or any government portal.
        </p>
      </div>
    </footer>
  );
}

export function Home() {
  return (
    <main id="main">
      <Hero />
      <Showcase />
      <HowItWorks />
      <Roles />
      <Footer />
    </main>
  );
}
