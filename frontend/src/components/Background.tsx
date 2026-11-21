/** Fixed navy backdrop with three slowly drifting colour orbs. Drift stops under reduced motion. */
export function Background() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="orb animate-drift-a left-[-10vw] top-[-12vh] h-[55vh] w-[55vh] bg-saffron/60" />
      <div className="orb animate-drift-b right-[-12vw] top-[20vh] h-[60vh] w-[60vh] bg-aqua/45" />
      <div className="orb animate-drift-c bottom-[-20vh] left-[25vw] h-[65vh] w-[65vh] bg-violet/55" />
      {/* soft vignette keeps text contrast high over the orbs */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,rgba(10,18,48,0.55)_75%)]" />
    </div>
  );
}
