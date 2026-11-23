import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { TrendPoint } from "../lib/api";
import { formatTime } from "./ui";

/**
 * Readiness after each validation run: one series, so the title names it and there is no legend.
 * 2px line, 8px markers with a 2px surface ring, only the latest value labelled, a crosshair
 * tooltip on hover and keyboard focus, and a table view for every value.
 */
const CAUSE: Record<string, string> = {
  "data.load": "Synthetic data loaded",
  "data.import": "School file imported",
  "issue.approve": "Fix approved",
  "issue.confirm": "Record confirmed as right",
  "issue.edit": "Value edited",
  "issue.hold": "Issue held",
  "issue.reject_suggestion": "Suggestion rejected",
  "demo.reset": "Demo reset",
};

export function causeLabel(p: TrendPoint): string {
  if (!p.cause) return "Validation run";
  const what = CAUSE[p.cause.action] ?? p.cause.action;
  const rec = p.cause.record?.replace(/^student:|^school:/, "");
  return `${what}${p.cause.rule_id ? ` (${p.cause.rule_id}` : ""}${p.cause.rule_id && rec ? `, ${rec})` : p.cause.rule_id ? ")" : ""}`;
}

const H = 150;
const PAD = { top: 18, right: 44, bottom: 22, left: 36 };
const SURFACE = "#16224f";

export function TrendChart({ points, title = "Readiness over time" }: { points: TrendPoint[]; title?: string }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(600);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(240, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const n = points.length;
  const values = points.map((p) => p.readiness);
  const lo = Math.max(0, Math.floor((Math.min(...values, 100) - 5) / 10) * 10);
  const hi = 100;
  const ticks = [lo, Math.round((lo + hi) / 2 / 5) * 5, hi];
  const iw = w - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw);
  const y = (v: number) => PAD.top + (1 - (v - lo) / (hi - lo)) * ih;
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.readiness).toFixed(1)}`).join(" ");

  const pick = (e: PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - r.left + PAD.left;
    const i = n <= 1 ? 0 : Math.round(((px - PAD.left) / iw) * (n - 1));
    setHover(Math.min(n - 1, Math.max(0, i)));
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      setHover((h) => Math.min(n - 1, Math.max(0, (h ?? n - 1) + (e.key === "ArrowRight" ? 1 : -1))));
    }
    if (e.key === "Escape") setHover(null);
  };

  const first = points[0];
  const last = points[n - 1];
  const hp = hover !== null ? points[hover] : null;
  const summary = n
    ? `${title}: ${first.readiness}% at the first validation run, ${last.readiness}% now, over ${n} run${n === 1 ? "" : "s"}.`
    : `${title}: no validation runs yet.`;

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-lg font-semibold text-cream">{title}</h2>
        {n > 1 && (
          <p className="text-sm text-mist">
            {first.readiness}% → <span className="font-semibold text-cream">{last.readiness}%</span> over {n} runs
          </p>
        )}
      </div>
      {n <= 1 && <p className="mt-1 text-xs text-mist">One run so far. Each approved fix re-runs validation and adds a point.</p>}
      <div ref={wrap} className="relative mt-2">
        <svg width={w} height={H} role="img" aria-label={summary} className="block overflow-visible">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={w - PAD.right} y1={y(t)} y2={y(t)} stroke="rgba(255,255,255,0.10)" strokeWidth={1} />
              <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize={11} fill="var(--color-mist, #b6bdd8)">{t}%</text>
            </g>
          ))}
          {hp && hover !== null && (
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + ih} stroke="rgba(247,240,225,0.45)" strokeWidth={1} />
          )}
          {n > 1 && <path d={path} fill="none" stroke="#FFB43B" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />}
          {points.map((p, i) => (
            <circle key={p.audit_id} cx={x(i)} cy={y(p.readiness)} r={hover === i ? 5.5 : 4} fill="#FFB43B" stroke={SURFACE} strokeWidth={2} />
          ))}
          {n > 0 && (
            <text x={x(n - 1) + 9} y={y(last.readiness)} dy="0.32em" fontSize={12} fontWeight={600} fill="#F7F0E1">{last.readiness}%</text>
          )}
          <text x={PAD.left} y={H - 4} fontSize={11} fill="var(--color-mist, #b6bdd8)">{n ? formatTime(first.ts) : ""}</text>
          {n > 1 && <text x={w - PAD.right} y={H - 4} textAnchor="end" fontSize={11} fill="var(--color-mist, #b6bdd8)">latest</text>}
          <rect
            x={PAD.left - 12} y={0} width={iw + 24} height={H} fill="transparent"
            tabIndex={0} role="slider" aria-label="Step through validation runs with the arrow keys"
            aria-valuemin={1} aria-valuemax={Math.max(1, n)} aria-valuenow={(hover ?? n - 1) + 1}
            aria-valuetext={hp ? `${hp.readiness}% after: ${causeLabel(hp)}` : summary}
            onPointerMove={pick} onPointerLeave={() => setHover(null)} onFocus={() => setHover(n - 1)} onBlur={() => setHover(null)} onKeyDown={onKey}
            className="cursor-crosshair outline-none focus-visible:stroke-saffron"
          />
        </svg>
        {hp && hover !== null && (
          <div
            className="pointer-events-none absolute z-10 w-56 rounded-xl border border-white/15 bg-bg-deep/95 p-3 text-xs shadow-xl"
            style={{ left: Math.min(Math.max(0, x(hover) - 112), w - 224), top: Math.max(0, y(hp.readiness) - 92) }}
          >
            <p className="flex items-center gap-2">
              <span className="inline-block h-0.5 w-3 rounded bg-saffron" aria-hidden />
              <span className="font-display text-base font-bold text-cream">{hp.readiness}%</span>
              <span className="text-mist">readiness</span>
            </p>
            <p className="mt-1 text-cream">{causeLabel(hp)}</p>
            <p className="text-mist">{hp.cause?.actor ? `${hp.cause.actor} · ` : ""}{formatTime(hp.ts)}</p>
          </div>
        )}
      </div>
      <details className="mt-2 text-xs text-mist">
        <summary className="cursor-pointer hover:text-cream focus-visible:outline-2 focus-visible:outline-saffron">Show as table</summary>
        <table className="mt-2 w-full text-left">
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr><th scope="col" className="py-1 pr-3 font-semibold">Run</th><th scope="col" className="py-1 pr-3 font-semibold">When</th><th scope="col" className="py-1 pr-3 font-semibold">After</th><th scope="col" className="py-1 font-semibold">Readiness</th></tr>
          </thead>
          <tbody>
            {points.map((p, i) => (
              <tr key={p.audit_id} className="border-t border-white/5">
                <td className="py-1 pr-3">{i + 1}</td>
                <td className="py-1 pr-3">{formatTime(p.ts)}</td>
                <td className="py-1 pr-3 text-cream">{causeLabel(p)}</td>
                <td className="py-1 font-semibold text-cream">{p.readiness}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
