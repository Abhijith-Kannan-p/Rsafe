import { Link } from "react-router-dom";
import { GlassCard } from "../components";

export function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center p-6">
      <GlassCard padding="lg" className="max-w-md text-center">
        <h1 className="text-3xl font-bold">Page not found</h1>
        <p className="mt-2 text-mist">That address does not exist in this prototype.</p>
        <Link to="/" className="mt-6 inline-block font-semibold text-saffron underline-offset-4 hover:underline">
          Back to start
        </Link>
      </GlassCard>
    </main>
  );
}
