import { Component, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="min-h-[200px] flex flex-col items-center justify-center p-8 border border-red-400/30 bg-red-400/5">
          <AlertTriangle className="w-8 h-8 text-red-400 mb-4" />
          <div className="font-['Rajdhani'] font-700 text-lg text-foreground mb-2">Une erreur est survenue</div>
          <div className="font-['JetBrains_Mono'] text-xs text-muted-foreground mb-4 max-w-md text-center">
            {this.state.error?.message ?? "Erreur inconnue"}
          </div>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
            className="flex items-center gap-2 px-4 py-2 font-['JetBrains_Mono'] text-xs border border-primary/30 text-primary hover:bg-primary/5 transition-all"
          >
            <RefreshCw className="w-3 h-3" />
            RECHARGER
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
