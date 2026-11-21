import { AnimatePresence, motion } from "framer-motion";
import { AlertOctagon, CheckCircle2, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { cn } from "../lib/cn";

type Kind = "success" | "error" | "info";
type ToastItem = { id: number; kind: Kind; title: string; body?: string };
type Ctx = { toast: (t: Omit<ToastItem, "id">) => void };

const ToastContext = createContext<Ctx | null>(null);

const STYLE: Record<Kind, { Icon: typeof Info; cls: string }> = {
  success: { Icon: CheckCircle2, cls: "text-aqua" },
  error: { Icon: AlertOctagon, cls: "text-coral" },
  info: { Icon: Info, cls: "text-violet" },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);

  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const toast = useCallback(
    (t: Omit<ToastItem, "id">) => {
      const id = next.current++;
      setItems((xs) => [...xs.slice(-3), { ...t, id }]);
      window.setTimeout(() => dismiss(id), 4500);
    },
    [dismiss],
  );
  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div aria-live="polite" aria-atomic="false" className="pointer-events-none fixed bottom-5 right-5 z-[60] flex w-[min(380px,calc(100vw-2.5rem))] flex-col gap-3">
        <AnimatePresence initial={false}>
          {items.map((t) => {
            const { Icon, cls } = STYLE[t.kind];
            return (
              <motion.div
                key={t.id}
                layout
                initial={{ opacity: 0, y: 16, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, x: 40 }}
                role={t.kind === "error" ? "alert" : "status"}
                className="glass pointer-events-auto flex items-start gap-3 !bg-bg-mid/85 p-4"
              >
                <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", cls)} aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-cream">{t.title}</p>
                  {t.body && <p className="mt-0.5 text-sm text-mist">{t.body}</p>}
                </div>
                <button
                  type="button"
                  aria-label="Dismiss notification"
                  onClick={() => dismiss(t.id)}
                  className="rounded-full p-1 text-mist hover:bg-white/10 hover:text-cream"
                >
                  <X className="h-4 w-4" aria-hidden />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx.toast;
}
