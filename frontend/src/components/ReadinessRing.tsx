import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "framer-motion";
import { useEffect, useId, useState } from "react";

type Props = {
  value: number; // 0-100
  size?: number;
  stroke?: number;
  label?: string;
};

function colourFor(v: number) {
  if (v >= 85) return "var(--aqua)";
  if (v >= 60) return "var(--saffron)";
  return "var(--coral)";
}

/** Animated readiness score ring. Colour: coral < 60 <= saffron < 85 <= aqua. */
export function ReadinessRing({ value, size = 180, stroke = 14, label = "Readiness" }: Props) {
  const clamped = Math.max(0, Math.min(100, value));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const reduce = useReducedMotion();
  const progress = useMotionValue(reduce ? clamped : 0);
  const dash = useTransform(progress, (p) => c - (p / 100) * c);
  const [shown, setShown] = useState(reduce ? clamped : 0);
  const gradId = "ring" + useId().replace(/[^a-zA-Z0-9]/g, "");

  useEffect(() => {
    if (reduce) {
      progress.set(clamped);
      setShown(clamped);
      return;
    }
    const controls = animate(progress, clamped, {
      duration: 1.2,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setShown(Math.round(v)),
    });
    return () => controls.stop();
  }, [clamped, reduce, progress]);

  const colour = colourFor(clamped);

  return (
    <div
      className="relative inline-grid place-items-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${label}: ${clamped} percent`}
    >
      <svg width={size} height={size} className="-rotate-90 overflow-visible">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={colour} />
            <stop offset="100%" stopColor={colour} stopOpacity={0.7} />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={`url(#${gradId})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          style={{ strokeDashoffset: dash, filter: `drop-shadow(0 0 10px ${colour})` }}
        />
      </svg>
      <div className="absolute text-center" aria-hidden>
        <div className="font-display text-4xl font-bold text-cream" style={{ fontSize: size * 0.24 }}>
          {shown}
          <span className="text-[0.5em] text-mist">%</span>
        </div>
        <div className="text-xs uppercase tracking-[0.18em] text-mist">{label}</div>
      </div>
    </div>
  );
}
