import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { BrandMark } from "./components/BrandMark";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Icon, type IconName } from "./components/Icon";
import { ProgressBar } from "./components/Progress";
import Job, { type BatchMeta } from "./routes/Job";
import Settings from "./routes/Settings";
import SpotFix from "./routes/SpotFix";
import Translate, { basename, type TranslateForm } from "./routes/Translate";
import { mergeRetried } from "./components/NeedsAttention";
import {
  api,
  describeError,
  loadSettings,
  onExit,
  onLog,
  onProgress,
  providerConfigured,
  type ItemPages,
  type JobStatus,
  type PageRecord,
  type Progress,
  type StillSkipped,
} from "./lib/api";
import "./App.css";

/**
 * The shell: a sidebar of four views, the view, and a status strip.
 *
 * ponytail: four views behind a useState, not a router. Ceiling: no deep
 * links and no browser history, so a re-render cannot be linked to. Upgrade
 * path: react-router, which the job queue will want when it grows a history.
 *
 * The status strip is the one thing every view shares. The sidecar's progress
 * line lands there whichever view is up, so a folder job started from
 * Translate keeps moving in the corner while the user reads Settings.
 */

type View = "translate" | "job" | "spotfix" | "settings";
type SidecarState = "starting" | "ready" | "error";
type Theme = "system" | "light" | "dark";

const THEME_KEY = "mt.theme";
const THEMES: { id: Theme; icon: IconName; label: string }[] = [
  { id: "system", icon: "monitor", label: "Follow the system theme" },
  { id: "light", icon: "sun", label: "Light theme" },
  { id: "dark", icon: "moon", label: "Dark theme" },
];

function loadTheme(): Theme {
  try {
    const t = localStorage.getItem(THEME_KEY);
    if (t === "light" || t === "dark" || t === "system") return t;
  } catch {
    // No storage, no preference: system.
  }
  return "system";
}

/**
 * Record `p` and return the event to display: the latest one for the lowest
 * page of `p`'s item that has not been written yet, or `p` itself when no
 * page of that item is still in flight (its last write, and the item events).
 * Keyed on `item_id`: on a page stage `item` is that stage's detail text, so
 * keying on it left every page's earlier stages behind in the map.
 */
function frontPage(pages: Map<string, Progress>, p: Progress): Progress {
  if (p.stage === "item_start" || p.stage === "item_done") {
    const prefix = `${p.item}\u001f`;
    for (const k of [...pages.keys()]) if (k.startsWith(prefix)) pages.delete(k);
    return p;
  }
  if (p.page <= 0) return p;
  const prefix = `${p.item_id ?? ""}\u001f`;
  const key = `${prefix}${p.page}`;
  if (p.stage === "write") pages.delete(key);
  else pages.set(key, p);
  let front: Progress | undefined;
  for (const [k, e] of pages) {
    if (k.startsWith(prefix) && (!front || e.page < front.page)) front = e;
  }
  return front ?? p;
}

/** The two bracketing lines read better as words than as identifiers. */
function stageWord(stage: string): string {
  return stage === "item_start" ? "starting" : stage === "item_done" ? "done" : stage;
}

const HEALTH_MS = 500;
const HEALTH_GIVE_UP_MS = 120_000;

function exitMessage(code: number | null): string {
  return (
    `The sidecar this app started has exited (code ${code ?? "killed"}). ` +
    "If the Log says port 8756 is already in use, a sidecar from an earlier run is " +
    "still running: end sidecar.exe in Task Manager, then restart the app."
  );
}

export default function App() {
  const [view, setView] = useState<View>("translate");
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const [sidecar, setSidecar] = useState<SidecarState>("starting");
  const [progress, setProgress] = useState<Progress | null>(null);
  // The newest event per (item, page) still short of `write`. The sidecar runs
  // an item's pages three at a time, so the raw stream interleaves them --
  // page 2 translating, page 3 detecting, page 2 erasing -- and a strip that
  // showed the last line received would jump between pages and run its stage
  // pips backwards. It shows the earliest unfinished page of the item instead.
  const inFlight = useRef(new Map<string, Progress>());
  const [log, setLog] = useState<string[]>([]);
  const [showLog, setShowLog] = useState(false);
  const [error, setError] = useState("");
  // Set by the sidecar-exit event; undefined while our child is alive.
  const exitCode = useRef<number | null | undefined>(undefined);

  const [form, setForm] = useState<TranslateForm>({
    paths: [],
    dest: "",
    source: "ja",
    lang: "en",
  });
  const [busy, setBusy] = useState(false);
  // Bumped when the first-run setup saves a provider, so Translate re-reads it.
  const [, setSettingsSeen] = useState(0);
  const [runningItems, setRunningItems] = useState<Set<string>>(new Set());

  // The queue's latest status (the Queue view polls and reports it here, so
  // the Editor's item switcher sees the same items), and what the run was
  // started with: its title, its languages, its output folder.
  const [batch, setBatch] = useState<JobStatus | null>(null);
  const [batchMeta, setBatchMeta] = useState<BatchMeta | null>(null);
  // The item open in the Editor, its pages, and the page on screen.
  // `manualPage` opens that page in hand-translation mode.
  const [editor, setEditor] = useState<ItemPages | null>(null);
  const [page, setPage] = useState<PageRecord | null>(null);
  const [manualPage, setManualPage] = useState<number | null>(null);

  // The CSS keys every light token on data-theme="light"; "system" is
  // resolved here so the stylesheet never has to know about the OS.
  useEffect(() => {
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // Not persisted; still applied.
    }
    const mq = matchMedia("(prefers-color-scheme: light)");
    const apply = () => {
      document.documentElement.dataset.theme =
        theme === "system" ? (mq.matches ? "light" : "dark") : theme;
    };
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [theme]);

  useEffect(() => {
    // Subscribe BEFORE starting, or the sidecar's first lines land before
    // anyone is listening and the bar sits empty through the opening stages.
    const subs = [
      onProgress((p) => {
        setProgress(frontPage(inFlight.current, p));
        if (p.stage === "item_start" || p.stage === "item_done") {
          setRunningItems((prev) => {
            const next = new Set(prev);
            if (p.stage === "item_start") next.add(p.item);
            else next.delete(p.item);
            return next;
          });
        }
      }),
      onLog((line) => setLog((prev) => [...prev.slice(-199), line])),
      onExit((code) => {
        // The sidecar this app started is gone, and nothing here restarts
        // it. If the strip already said "ready", whatever answered
        // /api/health was not ours -- a sidecar left over from an earlier
        // run, holding the port -- and every request from here on goes to
        // a process this app cannot see or stop. Either way: error, now,
        // rather than two minutes of polling or a 500 that points at the
        // wrong thing.
        exitCode.current = code;
        setSidecar("error");
        setError((prev) => prev || exitMessage(code));
      }),
    ];

    // start_sidecar returns on spawn, not on readiness. Readiness is the
    // health route answering, so poll it until it does.
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const began = Date.now();
    const poll = async () => {
      if (cancelled) return;
      try {
        await api.health();
        if (!cancelled) setSidecar("ready");
      } catch {
        if (Date.now() - began > HEALTH_GIVE_UP_MS) {
          if (!cancelled) {
            setSidecar("error");
            setError(
              exitCode.current !== undefined
                ? exitMessage(exitCode.current)
                : "The sidecar did not answer within two minutes. Open the log below.",
            );
          }
          return;
        }
        timer = setTimeout(poll, HEALTH_MS);
      }
    };
    api
      .start()
      .then(poll)
      .catch((e) => {
        setSidecar("error");
        setError(describeError(e));
      });

    // No api.stop() here. React never runs this cleanup when the window
    // closes -- the sidecar ends then because the process ending closes its
    // stdin pipe (lib.rs spawn, sidecar/main.py watch_parent). The cleanup
    // DOES run on StrictMode's dev double-mount and on HMR, and a stop there
    // killed a sidecar that was still importing torch, then raced the
    // re-mount's start for the same slot: on every dev launch this app
    // either had no sidecar or, before today, an orphan answering for it.
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      subs.forEach((p) => p.then((un) => un()));
    };
  }, []);

  /**
   * A run with no provider configured is refused here. The sidecar still has
   * its offline path -- the checks use it -- but from the UI that path wrote
   * "HELLO" into every bubble of the user's chapter and called it done.
   */
  function refuseUnconfigured(): boolean {
    if (providerConfigured()) return false;
    setError("No model is set up yet. Open Settings, enter the endpoint and a model, then run again.");
    return true;
  }

  /** Appends paths not already in the list (case-insensitively, as Windows
   *  compares them), against the CURRENT list: a drop lands after renders. */
  const addPaths = useCallback((paths: string[]) => {
    setForm((prev) => {
      const seen = new Set(prev.paths.map((x) => x.toLowerCase()));
      const fresh = paths.filter((x) => {
        const k = x.toLowerCase();
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      });
      return fresh.length ? { ...prev, paths: [...prev.paths, ...fresh] } : prev;
    });
  }, []);

  /** Plan 3.1: every run goes through the queue, one file or fifty. */
  async function runJob() {
    if (refuseUnconfigured()) return;
    setBusy(true);
    setError("");
    setProgress(null);
    inFlight.current.clear();
    try {
      // Before the run: the Editor loads pages from the output folder through
      // the asset protocol, and only folders allowed here can be read.
      await api.allowOutputDir(form.dest);
      const settings = loadSettings();
      const status = await api.job.start({
        // Minted here and kept: it is the address every later edit, retry
        // and resume uses, and a server-minted id the UI only learns from a
        // response it might not receive is an orphan.
        job_id: `job-${Date.now()}`,
        paths: form.paths,
        dest_dir: form.dest,
        source: form.source,
        lang: form.lang,
        settings,
      });
      const n = form.paths.length;
      const now = Date.now();
      setBatch(status);
      setBatchMeta({
        job_id: status.job_id,
        title: n === 1 ? basename(form.paths[0]) : `${basename(form.paths[0])} and ${n - 1} more`,
        started: now,
        source: form.source,
        lang: form.lang,
        dest: form.dest,
        // Nothing to translate: the start answers already done.
        finished: status.done && !status.paused && !status.cancelled ? now : undefined,
      });
      setView("job");
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  // The latest openItem call: an earlier reply arriving after a later one
  // (arrow keys on the chapter switcher) must not open the earlier choice.
  const openSeq = useRef(0);
  // The page cache's folder, allowed once for the asset protocol: the
  // Editor's original/translated toggle loads each page's original.jpg there.
  const cacheAllowed = useRef(false);

  /** Allow the page cache's folder for the asset protocol. The root comes
   *  from health, which is cheap; a sidecar built before health carried it
   *  is asked for the cache stats, which walk the cache. */
  async function allowCache() {
    try {
      const root = (await api.health()).cache_root ?? (await api.cache.stats()).root;
      await api.allowOutputDir(root);
      cacheAllowed.current = true;
    } catch {
      // Without it the strip falls back to the delivered pages and the
      // toggle is off; editing still works.
    }
  }

  /** Open one item of the queue in the Editor. Throws for the caller to show. */
  async function openItem(itemId: string, ordinal?: number, manual = false) {
    if (!batch) return;
    const seq = ++openSeq.current;
    const allowing = cacheAllowed.current ? null : allowCache();
    const item = await api.job.item(batch.job_id, itemId);
    await allowing;
    if (seq !== openSeq.current) return;
    if (item.pages.length === 0) {
      throw new Error(`${itemId} has no pages to open yet.`);
    }
    setEditor(item);
    setPage(item.pages.find((p) => p.page === ordinal) ?? item.pages[0]);
    setManualPage(manual && ordinal !== undefined ? ordinal : null);
    setView("spotfix");
  }

  /** Turning the page in the Editor. Stable, so the Editor's key listeners
   *  are not re-subscribed on every progress event of a run. */
  const selectPage = useCallback((p: PageRecord) => {
    setPage(p);
    setManualPage(null);
  }, []);

  /** Every status snapshot, from either poller. A late one of an earlier job
   *  is dropped. The meta keeps the time spent paused, and the first snapshot
   *  that shows the run finished stamps it, for the Queue's "finished in". */
  const noteBatch = useCallback((s: JobStatus) => {
    setBatch((prev) => (prev && prev.job_id !== s.job_id ? prev : s));
    setBatchMeta((m) => {
      if (!m || m.job_id !== s.job_id) return m;
      const now = Date.now();
      if (s.paused) return m.pausedSince == null ? { ...m, pausedSince: now } : m;
      const resumed =
        m.pausedSince == null
          ? m
          : { ...m, pausedSince: undefined, pausedMs: (m.pausedMs ?? 0) + now - m.pausedSince };
      return s.done && !s.cancelled && resumed.finished == null ? { ...resumed, finished: now } : resumed;
    });
  }, []);

  /** The queue's counts after a fix in the Editor: the Queue view and the
   *  chapter switcher read them, and the Queue only polls while it runs. */
  async function refreshBatch() {
    if (!batch) return;
    try {
      noteBatch(await api.job.status(batch.job_id));
    } catch {
      // The Queue view reports a sidecar that stopped answering.
    }
  }

  /** Replace one page of the open item with the server's fresh record. */
  function updatePage(fresh: PageRecord) {
    if (!fresh.skipped) void refreshBatch();
    // A reply that lands after the user moved on -- another page, another
    // chapter -- updates its own record and drags nobody back (review).
    setPage((prev) =>
      prev && prev.item_id === fresh.item_id && prev.page === fresh.page ? fresh : prev,
    );
    setEditor((prev) =>
      prev && prev.item_id === fresh.item_id
        ? { ...prev, pages: prev.pages.map((p) => (p.page === fresh.page ? fresh : p)) }
        : prev,
    );
  }

  /** Pages a retry brought back: fixed ones replace their records. */
  function retriedPages(results: (PageRecord | StillSkipped)[]) {
    void refreshBatch();
    const mine = (id: string) => results.filter((r) => r.item_id === id);
    setEditor((prev) =>
      prev ? { ...prev, pages: mergeRetried(prev.pages, mine(prev.item_id)) } : prev,
    );
    setPage((prev) => (prev ? (mergeRetried([prev], mine(prev.item_id))[0] ?? prev) : prev));
  }

  // While the job runs and the Queue view is not the one polling, keep its
  // status fresh here: the Editor's switcher lists items as they finish, and
  // its retry and hand actions know when the sidecar would refuse them.
  useEffect(() => {
    if (!batch || batch.done || view === "job") return;
    const t = setInterval(() => void refreshBatch(), 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch?.job_id, batch?.done, view]);

  // Guarded: this runs outside the per-view ErrorBoundary, so a page record
  // without a fit summary would blank the whole window rather than one view.
  const failedPages =
    editor?.pages.filter((p) => (p.fit_summary?.fit_failed?.length ?? 0) > 0).length ?? 0;
  // A run is live while a request is out or an item is between its start and
  // done lines. Outside that, the strip says Idle instead of the last stage
  // it happened to see ("write · page 3 of 3" long after the run ended).
  const runActive = busy || runningItems.size > 0;

  const NAV: { id: View; label: string; icon: IconName; disabled?: boolean; badge?: ReactNode }[] = [
    { id: "translate", label: "Translate", icon: "languages" },
    {
      id: "job",
      label: "Queue",
      icon: "list",
      disabled: !batch,
      badge: runningItems.size > 0 ? <span className="badge live">{runningItems.size}</span> : undefined,
    },
    {
      id: "spotfix",
      label: "Editor",
      icon: "pencil",
      disabled: !editor,
      badge: failedPages > 0 ? <span className="badge alert">{failedPages}</span> : undefined,
    },
    { id: "settings", label: "Settings", icon: "sliders" },
  ];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <BrandMark size={28} />
          </span>
          <div>
            <div className="brand-name">Komalingo</div>
            <div className="brand-sub">local pipeline</div>
          </div>
        </div>
        <nav className="nav" aria-label="Views">
          {NAV.map((n) => (
            <button
              key={n.id}
              type="button"
              className="nav-item"
              onClick={() => setView(n.id)}
              disabled={n.disabled}
              aria-current={view === n.id ? "page" : undefined}
              title={n.disabled ? `${n.label} opens once something is translated` : undefined}
            >
              <Icon name={n.icon} />
              <span className="label">{n.label}</span>
              {n.badge}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="seg" role="radiogroup" aria-label="Theme">
            {THEMES.map((t) => (
              <button
                key={t.id}
                type="button"
                role="radio"
                aria-checked={theme === t.id}
                onClick={() => setTheme(t.id)}
                title={t.label}
              >
                <Icon name={t.icon} size={15} label={t.label} />
              </button>
            ))}
          </div>
          <span className="note">Nothing leaves this machine but the model calls.</span>
        </div>
      </aside>

      {/* Something moving while the sidecar boots. The strip already says
          "Starting sidecar…", but a first launch unpacks torch and can sit
          there ten seconds or more; a shell that is merely disabled for that
          long reads as hung. */}
      {sidecar === "starting" && (
        <div className="boot-line progress sm indeterminate" aria-hidden>
          <div className="fill" />
        </div>
      )}

      <main className="main">
        {/* Per view, keyed on the view: a crash in one leaves the sidebar
            standing, and moving to another view clears it. */}
        <ErrorBoundary scope="This view" resetKey={view}>
          {view === "settings" ? (
            <Settings />
          ) : view === "job" && batch && batchMeta ? (
            <Job
              key={batch.job_id}
              jobId={batch.job_id}
              initial={batch}
              meta={batchMeta}
              runningItems={runningItems}
              onStatus={noteBatch}
              onOpenItem={openItem}
              onOpenSettings={() => setView("settings")}
            />
          ) : view === "spotfix" && editor && page ? (
            <SpotFix
              key={`${editor.job_id}/${editor.item_id}`}
              item={editor}
              items={batch?.items ?? []}
              onSwitchItem={(id) => openItem(id)}
              page={page}
              onSelectPage={selectPage}
              onPage={updatePage}
              onRetried={retriedPages}
              manualPage={manualPage}
              onManualPage={setManualPage}
              blocked={
                batch && !batch.done
                  ? "The run is still going: retry and hand translation open when it finishes."
                  : batch?.paused
                    ? "The run is paused: resume or cancel it in the Queue first."
                    : ""
              }
            />
          ) : (
            <Translate
              form={form}
              onForm={(patch) => setForm((prev) => ({ ...prev, ...patch }))}
              onAddPaths={addPaths}
              busy={busy}
              sidecarReady={sidecar === "ready"}
              configured={providerConfigured()}
              onConfigured={() => {
                setSettingsSeen((n) => n + 1);
                // "No model is set up yet" no longer holds.
                setError("");
              }}
              onOpenSettings={() => setView("settings")}
              onRun={runJob}
              error={error}
            />
          )}
        </ErrorBoundary>
      </main>

      {showLog && (
        <section className="log-drawer" aria-label="Sidecar log">
          {log.length === 0 ? (
            <p className="empty mono">Nothing yet.</p>
          ) : (
            <pre>{log.join("\n")}</pre>
          )}
        </section>
      )}

      <footer className="statusbar">
        <div className="sidecar">
          <span className={`dot ${sidecar}`} aria-hidden />
          <span>
            {sidecar === "starting"
              ? "Starting sidecar…"
              : sidecar === "ready"
                ? "Sidecar ready"
                : "Sidecar failed"}
          </span>
        </div>
        <div className="live" aria-live="polite">
          {runActive && progress && progress.stage !== "item_done" ? (
            <>
              <span className="text">
                <strong>{stageWord(progress.stage)}</strong>
                {" · "}
                {progress.item}
                {progress.page > 0
                  ? progress.total
                    ? ` · page ${progress.page} of ${progress.total}`
                    : ` · page ${progress.page}`
                  : ""}
              </span>
              <span className="mini">
                <ProgressBar label="Current page" value={progress.pct} size="sm" />
              </span>
            </>
          ) : runActive && progress?.stage === "item_done" ? (
            <span className="text">
              <strong>done</strong> · {progress.item}
            </span>
          ) : (
            <span className="text faint">Idle</span>
          )}
        </div>
        <button
          type="button"
          className="btn ghost sm log-toggle"
          onClick={() => setShowLog((v) => !v)}
          aria-pressed={showLog}
          aria-expanded={showLog}
        >
          <Icon name="terminal" size={14} />
          Log
          <Icon name={showLog ? "chevron-down" : "chevron-up"} size={14} />
        </button>
      </footer>
    </div>
  );
}
