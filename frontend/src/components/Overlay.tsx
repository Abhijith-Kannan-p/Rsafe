import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "../lib/cn";

type Props = {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
};

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])';

/** Esc to close, focus moves in on open, Tab is trapped, focus returns to the opener on close. */
function useDialogBehaviour(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const node = ref.current;
    const first = node?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? node)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      } else if (e.key === "Tab" && node) {
        const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE));
        if (items.length === 0) return;
        const [a, b] = [items[0], items[items.length - 1]];
        if (e.shiftKey && document.activeElement === a) {
          e.preventDefault();
          b.focus();
        } else if (!e.shiftKey && document.activeElement === b) {
          e.preventDefault();
          a.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      opener?.focus?.();
    };
  }, [open, onClose]);
  return ref;
}

function Header({ id, title, onClose }: { id: string; title: ReactNode; onClose: () => void }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-white/10 px-6 py-4">
      <h2 id={id} className="text-lg font-semibold text-cream">
        {title}
      </h2>
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="grid h-9 w-9 place-items-center rounded-full text-mist transition hover:bg-white/10 hover:text-cream"
      >
        <X className="h-5 w-5" aria-hidden />
      </button>
    </div>
  );
}

const backdrop = (
  <motion.div
    className="absolute inset-0 bg-bg-deep/60 backdrop-blur-sm"
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
  />
);

export function Modal({ open, onClose, title, children, footer, className }: Props) {
  const ref = useDialogBehaviour(open, onClose);
  const titleId = useId();
  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
          {backdrop}
          <motion.div
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            className={cn("glass relative w-full max-w-lg !bg-bg-mid/80", className)}
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
          >
            <Header id={titleId} title={title} onClose={onClose} />
            <div className="px-6 py-5">{children}</div>
            {footer && <div className="flex justify-end gap-3 border-t border-white/10 px-6 py-4">{footer}</div>}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

export function SidePanel({ open, onClose, title, children, footer, className }: Props) {
  const ref = useDialogBehaviour(open, onClose);
  const titleId = useId();
  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
          {backdrop}
          <motion.aside
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            className={cn(
              "glass absolute right-0 top-0 flex h-full w-full max-w-xl flex-col !rounded-none !rounded-l-[20px] !bg-bg-mid/85",
              className,
            )}
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
          >
            <Header id={titleId} title={title} onClose={onClose} />
            <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
            {footer && <div className="flex flex-wrap justify-end gap-3 border-t border-white/10 px-6 py-4">{footer}</div>}
          </motion.aside>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
