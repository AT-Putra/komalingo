import { useEffect, useState } from "react";
import Settings from "./routes/Settings";
import { api, describeError, onLog, onProgress, type Progress } from "./lib/api";
import "./App.css";

/**
 * Phase 0 shell: start the sidecar, show its progress, reach Settings.
 *
 * ponytail: two views behind a useState, not a router. Ceiling: no deep links
 * and no browser history. Upgrade path: react-router when there is a third
 * view to reach.
 */
export default function App() {
  const [view, setView] = useState<"home" | "settings">("home");
  const [progress, setProgress] = useState<Progress | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    // Subscribe BEFORE starting, or the sidecar's first lines land before
    // anyone is listening and the bar sits empty through the opening stages.
    const subs = [
      onProgress(setProgress),
      onLog((line) => setLog((prev) => [...prev.slice(-49), line])),
    ];
    api.start().catch((e) => setError(describeError(e)));
    return () => {
      subs.forEach((p) => p.then((un) => un()));
      api.stop().catch(() => {
        // Closing anyway; the Rust side kills the child if the POST is missed.
      });
    };
  }, []);

  return (
    <main className="container">
      <nav className="row">
        <button onClick={() => setView("home")} disabled={view === "home"}>
          Home
        </button>
        <button onClick={() => setView("settings")} disabled={view === "settings"}>
          Settings
        </button>
      </nav>

      {view === "settings" ? (
        <Settings />
      ) : (
        <section>
          <h1>MangaTranslator</h1>
          {error && <pre className="error">{error}</pre>}
          {progress ? (
            <p>
              {progress.stage} — {progress.item} ({progress.pct}%)
            </p>
          ) : (
            <p>Starting the sidecar…</p>
          )}
          <pre className="log">{log.join("\n")}</pre>
        </section>
      )}
    </main>
  );
}
