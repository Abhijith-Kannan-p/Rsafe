import { motion } from "framer-motion";
import { ArrowRight, type LucideIcon } from "lucide-react";
import { Button } from "./Button";

type Props = {
  icon: LucideIcon;
  title: string;
  description: string;
  accent?: "saffron" | "aqua" | "violet" | "coral";
  onEnter: () => void;
};

const ACCENT = {
  saffron: "text-saffron bg-saffron/15 ring-saffron/30",
  aqua: "text-aqua bg-aqua/15 ring-aqua/30",
  violet: "text-violet bg-violet/15 ring-violet/30",
  coral: "text-coral bg-coral/15 ring-coral/30",
} as const;

export function RoleCard({ icon: Icon, title, description, accent = "saffron", onEnter }: Props) {
  return (
    <motion.article
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 300, damping: 22 }}
      className="glass flex h-full flex-col gap-4 p-6"
    >
      <div className={`grid h-12 w-12 place-items-center rounded-2xl ring-1 ring-inset ${ACCENT[accent]}`}>
        <Icon className="h-6 w-6" aria-hidden />
      </div>
      <div className="flex-1">
        <h3 className="text-lg font-semibold text-cream">{title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-mist">{description}</p>
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={onEnter}
        iconRight={<ArrowRight className="h-4 w-4" aria-hidden />}
        aria-label={`Enter as ${title}`}
        className="self-start"
      >
        Enter
      </Button>
    </motion.article>
  );
}
