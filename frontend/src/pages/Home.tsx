import { motion } from "framer-motion";
import { Palette } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components";
import { MOTTO, SYNTHETIC_LINE } from "../copy";

/** Phase 1 placeholder. The full landing experience (hero, scroll showcase, roles) lands in Phase 7. */
export function Home() {
  const navigate = useNavigate();
  return (
    <main className="grid min-h-screen place-items-center px-6 text-center">
      <div>
        <motion.h1
          initial={{ opacity: 0, y: 24, filter: "blur(12px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 1.6, ease: [0.22, 1, 0.36, 1] }}
          className="text-7xl font-bold text-cream sm:text-8xl"
        >
          Rsafe
        </motion.h1>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2, duration: 0.9 }}
          className="mt-4 text-xl text-sand"
        >
          {MOTTO}
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.9, duration: 0.6 }}
          className="mt-10 flex flex-col items-center gap-4"
        >
          <Button size="lg" icon={<Palette className="h-5 w-5" aria-hidden />} onClick={() => navigate("/styleguide")}>
            View design system
          </Button>
          <p className="text-sm text-mist">{SYNTHETIC_LINE} Full landing page arrives in Phase 7.</p>
        </motion.div>
      </div>
    </main>
  );
}
