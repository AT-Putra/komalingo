/**
 * The floor under a render error.
 *
 * React unmounts the whole tree when a component throws during render and
 * nothing catches it -- the window goes blank, with no message and no way
 * back short of restarting the app. This catches it, reports it (console, and
 * the terminal in dev -- see lib/report.ts), and draws something the user
 * can read and act on: the error, where it happened, and two ways out.
 *
 * Used at two depths. main.tsx wraps the whole app, full-screen, for a crash
 * in the shell itself. App.tsx wraps the current view with `resetKey={view}`,
 * so a crash in Settings leaves the sidebar standing and switching views
 * recovers without a reload.
 *
 * A class, because componentDidCatch has no hook equivalent.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";
import { Icon } from "./Icon";
import { reportError } from "../lib/report";

interface Props {
  children: ReactNode;
  /** What broke, as the user sees it: "The app", "This view". */
  scope: string;
  /** Cover the window rather than the parent box. */
  full?: boolean;
  /** Changing this clears a caught error -- the user navigated away. */
  resetKey?: unknown;
}

interface State {
  error: Error | null;
  where: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, where: "" };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    const where = (info.componentStack ?? "").trim();
    this.setState({ where });
    reportError("render", error, where);
  }

  componentDidUpdate(prev: Props) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) {
      this.setState({ error: null, where: "" });
    }
  }

  render() {
    const { error, where } = this.state;
    if (!error) return this.props.children;
    return (
      <div className={`crash${this.props.full ? " full" : ""}`} role="alert">
        <div className="crash-card">
          <div className="card-head">
            <span className="icon-tile danger">
              <Icon name="alert-triangle" />
            </span>
            <div>
              <h2>{this.props.scope} hit an error</h2>
              <p className="sub">
                Settings and finished runs are untouched. The text below is what to put
                in a bug report.
              </p>
            </div>
          </div>
          <pre className="crash-msg">
            {error.name}: {error.message}
          </pre>
          {where && (
            <details className="crash-where">
              <summary>Where it happened</summary>
              <pre>{where}</pre>
            </details>
          )}
          <div className="crash-actions">
            <button
              type="button"
              className="btn primary"
              onClick={() => this.setState({ error: null, where: "" })}
            >
              <Icon name="refresh" />
              Try again
            </button>
            <button type="button" className="btn" onClick={() => location.reload()}>
              Reload the app
            </button>
          </div>
        </div>
      </div>
    );
  }
}
