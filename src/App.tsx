import { useEffect, useState, type ReactNode } from "react";
import { Icon, type IconName } from "./components/Icon";
import { ProgressBar } from "./components/Progress";
import Job from "./routes/Job";
import Settings from "./routes/Settings";
import SpotFix from "./routes/SpotFix";
import Translate, { type Busy, type TranslateForm } from "./routes/Translate";
import {
  api,
  describeError,
  loadSettings,
  onLog,
  onProgress,
  type ItemResult,
  type JobStatus,
  type PageRecord,
  type Progress,
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

/** The two bracketing lines read better as words than as identifiers. */
function stageWord(stage: string): string {
  return stage === "item_start" ? "starting" : stage === "item_done" ? "done" : stage;
}

const HEALTH_MS = 500;
const HEALTH_GIVE_UP_MS = 120_000;

export default function App() {
  const [view, setView] = useState<View>("translate");
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const [sidecar, setSidecar] = useState<SidecarState>("starting");
  const [progress, setProgress] = useState<Progress | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [showLog, setShowLog] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState<TranslateForm>({
    src: "",
    folder: "",
    dest: "",
    source: "ja",
    lang: "en",
  });
  const [busy, setBusy] = useState<Busy>("");
  const [pagesDone, setPagesDone] = useState(0);
  const [runningItems, setRunningItems] = useState<Set<string>>(new Set());

  const [batch, setBatch] = useState<JobStatus | null>(null);
  const [job, setJob] = useState<ItemResult | null>(null);
  const [page, setPage] = useState<PageRecord | null>(null);

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
        setProgress(p);
        if (p.stage === "write") setPagesDone((n) => n + 1);
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
            setError("The sidecar did not answer within two minutes. Open the log below.");
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

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      subs.forEach((p) => p.then((un) => un()));
      api.stop().catch(() => {
        // Closing anyway; the Rust side kills the child if the POST is missed.
      });
    };
  }, []);

  async function runItem() {
    setBusy("item");
    setError("");
    setPagesDone(0);
    setProgress(null);
    try {
      const settings = loadSettings();
      const result = await api.item({
        src_path: form.src,
        dest_dir: form.dest,
        // The job id is minted here and kept, because it is the delete scope
        // and the address every later spot-fix uses. A server-minted id the UI
        // only learns from a response it might not receive is an orphan.
        job_id: `job-${Date.now()}`,
        source: form.source,
        lang: form.lang,
        settings: settings.base_url && settings.model ? settings : undefined,
      });
      setJob(result);
      setPage(result.pages[0] ?? null);
      setView("spotfix");
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy("");
    }
  }

  /** AC-7: every file in the folder, through the queue; the Job view polls. */
  async function runFolder() {
    setBusy("folder");
    setError("");
    setPagesDone(0);
    setProgress(null);
    try {
      const settings = loadSettings();
      const status = await api.job.start({
        job_id: `job-${Date.now()}`,
        dir: form.folder,
        dest_dir: form.dest,
        source: form.source,
        lang: form.lang,
        settings: settings.base_url && settings.model ? settings : undefined,
      });
      setBatch(status);
      setView("job");
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy("");
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

  const failedPages = job?.pages.filter((p) => p.fit_summary.fit_failed.length > 0).length ?? 0;

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
      disabled: !job,
      badge: failedPages > 0 ? <span className="badge alert">{failedPages}</span> : undefined,
    },
    { id: "settings", label: "Settings", icon: "sliders" },
  ];

  const warnings = [job?.cache_warning, job?.vision_warning].filter(
    (w): w is string => typeof w === "string" && w !== "",
  );

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Icon name="book" size={18} />
          </span>
          <div>
            <div className="brand-name">MangaTranslator</div>
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
              title={n.disabled ? `${n.label} appears after a run` : undefined}
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

      <main className="main">
        {view === "settings" ? (
          <Settings />
        ) : view === "job" && batch ? (
          <Job key={batch.job_id} jobId={batch.job_id} initial={batch} runningItems={runningItems} />
        ) : view === "spotfix" && job && page ? (
          <SpotFix
            job={job.job_id}
            page={page}
            pages={job.pages}
            onSelectPage={setPage}
            destDir={form.dest}
            lang={form.lang}
            onPage={updatePage}
          />
        ) : (
          <Translate
            form={form}
            onForm={(patch) => setForm((prev) => ({ ...prev, ...patch }))}
            busy={busy}
            sidecarReady={sidecar === "ready"}
            onRunItem={runItem}
            onRunFolder={runFolder}
            error={error}
            warnings={warnings}
            progress={progress}
            pagesDone={pagesDone}
          />
        )}
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
          {progress && progress.stage !== "item_done" ? (
            <>
              <span className="text">
                <strong>{stageWord(progress.stage)}</strong>
                {" · "}
                {progress.item}
                {progress.page > 0 ? ` · page ${progress.page}` : ""}
              </span>
              <span className="mini">
                <ProgressBar label="Current page" value={progress.pct} size="sm" />
              </span>
            </>
          ) : progress?.stage === "item_done" ? (
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
