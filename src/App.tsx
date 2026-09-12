import { useEffect, useState } from "react";
import Settings from "./routes/Settings";
import SpotFix from "./routes/SpotFix";
import {
  api,
  describeError,
  loadSettings,
  onLog,
  onProgress,
  SOURCES,
  TARGETS,
  type ItemResult,
  type PageRecord,
  type Progress,
  type Source,
  type Target,
} from "./lib/api";
import "./App.css";

/**
 * Phase 0 shell, extended in Phase 3 to reach the spot-fix editor.
 *
 * ponytail: three views behind a useState, not a router. Ceiling: no deep
 * links and no browser history, so a re-render cannot be linked to. Upgrade
 * path: react-router, which Phase 8 will want anyway for the job queue.
 *
 * The archive path and destination are typed rather than picked from a dialog.
 * ponytail again. Ceiling: the user has to paste a path. Upgrade path: the
 * Tauri dialog plugin, which is a packaging scope change and belongs with the
 * one Phase 8 already makes.
 */
export default function App() {
  const [view, setView] = useState<"home" | "settings" | "spotfix">("home");
  const [progress, setProgress] = useState<Progress | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState("");

  const [src, setSrc] = useState("");
  const [dest, setDest] = useState("");
  const [source, setSource] = useState<Source>("ja");
  const [lang, setLang] = useState<Target>("en");
  const [job, setJob] = useState<ItemResult | null>(null);
  const [page, setPage] = useState<PageRecord | null>(null);
  const [busy, setBusy] = useState(false);

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

  async function runItem() {
    setBusy(true);
    setError("");
    try {
      const settings = loadSettings();
      const result = await api.item({
        src_path: src,
        dest_dir: dest,
        // The job id is minted here and kept, because it is the delete scope
        // and the address every later spot-fix uses. A server-minted id the UI
        // only learns from a response it might not receive is an orphan.
        job_id: `job-${Date.now()}`,
        source,
        lang,
        settings: settings.base_url && settings.model ? settings : undefined,
      });
      setJob(result);
      setPage(result.pages[0] ?? null);
      setView("spotfix");
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  /** Replace one page in the job with the server's fresh record after an edit. */
  function updatePage(fresh: PageRecord) {
    setPage(fresh);
    setJob((prev) =>
      prev
        ? {
            ...prev,
            pages: prev.pages.map((p) => (p.page === fresh.page ? fresh : p)),
          }
        : prev,
    );
  }

  return (
    <main className="container">
      <nav className="row">
        <button onClick={() => setView("home")} disabled={view === "home"}>
          Home
        </button>
        <button onClick={() => setView("settings")} disabled={view === "settings"}>
          Settings
        </button>
        <button
          onClick={() => setView("spotfix")}
          disabled={view === "spotfix" || !job}
        >
          Spot-fix
        </button>
      </nav>

      {view === "settings" ? (
        <Settings />
      ) : view === "spotfix" && job && page ? (
        <>
          <nav className="row pages">
            {job.pages.map((p) => (
              <button
                key={p.page}
                onClick={() => setPage(p)}
                disabled={p.page === page.page}
              >
                {p.page}
                {p.fit_summary.fit_failed.length > 0 ? " !" : ""}
              </button>
            ))}
          </nav>
          <SpotFix
            job={job.job_id}
            page={page}
            destDir={dest}
            lang={lang}
            onPage={updatePage}
          />
        </>
      ) : (
        <section>
          <h1>MangaTranslator</h1>
          {error && <pre className="error">{error}</pre>}

          <div className="row">
            <input
              value={src}
              onChange={(e) => setSrc(e.target.value)}
              placeholder="path to a .cbz or .pdf"
              size={40}
            />
            <input
              value={dest}
              onChange={(e) => setDest(e.target.value)}
              placeholder="output folder"
              size={30}
            />
            <select
              aria-label="source language"
              value={source}
              onChange={(e) => setSource(e.target.value as Source)}
            >
              {SOURCES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
            <select
              aria-label="target language"
              value={lang}
              onChange={(e) => setLang(e.target.value as Target)}
            >
              {TARGETS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
            <button onClick={runItem} disabled={busy || !src || !dest}>
              {busy ? "Translating…" : "Translate item"}
            </button>
          </div>

          {job?.cache_warning && <p className="warn">{job.cache_warning}</p>}

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
