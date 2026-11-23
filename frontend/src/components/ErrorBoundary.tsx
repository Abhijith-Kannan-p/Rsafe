import { AlertOctagon } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode; /** Changing this clears the error, e.g. on navigation. */ resetKey?: string };
type State = { error: Error | null };

/** Shows a calm message instead of a blank page if a screen fails to render. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.warn("Rsafe screen failed to render:", error, info.componentStack);
  }

  componentDidUpdate(prev: Props) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="glass mx-auto my-10 max-w-lg p-8 text-center">
        <AlertOctagon className="mx-auto h-10 w-10 text-coral" aria-hidden />
        <h1 className="mt-3 font-display text-2xl font-bold text-cream">This screen hit a problem</h1>
        <p className="mt-2 text-sm text-mist">
          Nothing was saved or changed. Reload to try again, or pick another screen.
        </p>
        <p className="mt-3 break-words font-mono text-xs text-mist/80">{this.state.error.message}</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-6 inline-flex h-11 items-center rounded-full bg-saffron px-5 font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-[3px] focus-visible:outline-saffron"
        >
          Reload
        </button>
      </div>
    );
  }
}
