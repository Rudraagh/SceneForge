/**
 * Catches render/runtime errors so a failed dependency (e.g. Plotly) does not leave a blank page.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class RootErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("SceneForge UI error:", error, info.componentStack);
  }

  override render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-[#f4f3ef] px-6 py-10 text-[#0c0c0c]">
          <h1 className="font-serif text-xl font-semibold">SceneForge could not start</h1>
          <p className="mt-2 max-w-xl text-sm text-[#404040]">
            Open DevTools (F12) → Console for details. If you recently changed dependencies, try{" "}
            <code className="rounded bg-black/5 px-1">cd frontend &amp;&amp; rm -rf node_modules &amp;&amp; npm install</code> then{" "}
            <code className="rounded bg-black/5 px-1">npm run dev</code>.
          </p>
          <pre className="mt-4 max-h-64 overflow-auto rounded border border-black/10 bg-white p-3 text-xs text-red-800">
            {this.state.error.message}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}
