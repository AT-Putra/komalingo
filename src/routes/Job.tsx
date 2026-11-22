/**
 * The queue (plan Phase 3.2): one row per chapter, its pages as they land,
 * and when the run is done, the pages it could not translate with the ways
 * to try them again.
 *
 * Polled, not pushed. The sidecar's stdout carries item_start / item_done
 * for the status strip, but each item's page counts, its skipped pages and
 * its reasons live in the job's status snapshot, and a snapshot every half
 * second is cheaper to get right than rebuilding the table from a stream of
 * events. Polling stops when the job says done, and starts again after a
 * resume because the resumed status is not done.
 *
 * The job's warnings are shown once, above the table: once per job is the
 * scope AC-6 gives the cbr->cbz warning.
 *
 * Status is never colour alone: every pill carries an icon and the word.
 */

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Alert } from "../components/Alert";
import { ErrorAlert } from "../components/ErrorAlert";
import { Icon, type IconName } from "../components/Icon";
import { mergeRetried, NeedsAttention } from "../components/NeedsAttention";
import { ProgressBar } from "../components/Progress";
import {
  api,
  describeError,
  displayPath,
  loadSettings,
  providerConfigured,
  SOURCES,
  TARGETS,
  type JobItem,
  type JobStatus,
  type PageRecord,
  type Source,
  type StillSkipped,
  type Target,
} from "../lib/api";

const POLL_MS = 500;

/** What a run was started with, kept by App beside the job's status. */
export interface BatchMeta {
  title: string;
  started: number;
  source: Source;
  lang: Target;
  dest: string;
  /** When a snapshot first showed the run finished, stamped by App: the
   *  Queue view unmounts while the Editor is open, and "finished in" has to
   *  survive that. Absent until then, and for a cancelled run. */
  finished?: number;
  /** The job this meta belongs to: a late snapshot of an earlier job must
   *  not stamp this one. */
  job_id: string;
  /** Time spent paused, and since when it is paused now: "finished in"
   *  counts the work, not a night waiting on a Resume. */
  pausedMs?: number;
  pausedSince?: number;
}

const PILL: Record<JobItem["status"], { icon: IconName; text: string }> = {
  pending: { icon: "clock", text: "Waiting" },
  ok: { icon: "check", text: "Done" },
  skipped: { icon: "skip-forward", text: "Not a chapter" },
  failed: { icon: "alert-circle", text: "Failed" },
  cancelled: { icon: "ban", text: "Cancelled" },
  paused: { icon: "pause", text: "Paused" },
};

const KIND_ICON: Record<JobItem["kind"], IconName> = {
  archive: "book",
  pdf: "file",
  images: "image",
  image: "image",
  unsupported: "file",
};

function StatusPill({ status, running }: { status: JobItem["status"]; running: boolean }) {
  if (running) {
    return (
      <span className="pill running">
        <Icon name="loader" size={12} />
        Translating
      </span>
    );
  }
  const p = PILL[status];
  return (
    <span className={`pill ${status}`}>
      <Icon name={p.icon} size={12} />
      {p.text}
    </span>
  );
}

/** "45 s", "3 min 12 s", "1 h 4 min". */
function duration(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min ${s % 60} s`;
  return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
}

function label<T extends string>(list: { value: T; label: string }[], v: T): string {
  return list.find((x) => x.value === v)?.label ?? v;
}

export default function Job({
  jobId,
  initial,
  meta,
  runningItems,
  onStatus,
  onOpenItem,
  onOpenSettings,
}: {
  jobId: string;
  initial: JobStatus;
  meta: BatchMeta;
  /** Item ids between an item_start and its item_done, from the event stream. */
  runningItems: Set<string>;
  /** Every fresh snapshot, so the Editor's item switcher sees the same items. */
  onStatus: (s: JobStatus) => void;
  /** Open an item in the Editor; rejects with a reason to show here. */
  onOpenItem: (itemId: string, ordinal?: number, manual?: boolean) => Promise<void>;
  onOpenSettings: () => void;
}) {
  const [status, setStatus] = useState<JobStatus>(initial);
  const [error, setError] = useState("");
  const [resuming, setResuming] = useState(false);
  /** The output folder in the file manager (plan 4.3). */
  async function reveal() {
    setError("");
    try {
      const { revealItemInDir } = await import("@tauri-apps/plugin-opener");
      await revealItemInDir(meta.dest);
    } catch (e) {
      setError(describeError(e));
    }
  }
  // The skipped page RECORDS of each finished item that has some, for the
  // review panels: thumbnails, the provider's words, the retry results.
  const [skippedPages, setSkippedPages] = useState<Record<string, PageRecord[]>>({});
  // Items whose last skipped page a retry just fixed: their panel closes,
  // and this says so where it stood, with the way into the Editor.
  const [cleared, setCleared] = useState<string[]>([]);
  // Read by `retried`, which runs after an await: the state it closed over
  // can be older than the panel's latest merge.
  const skippedRef = useRef(skippedPages);
  skippedRef.current = skippedPages;
  // Focus goes to the newest "every page is translated" notice: the panel the
  // user was working in has just closed under them.
  const clearedFocus = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (cleared.length) clearedFocus.current?.focus();
  }, [cleared.length]);

  function take(fresh: JobStatus) {
    setStatus(fresh);
    onStatus(fresh);
  }

  useEffect(() => {
    if (status.done) return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api.job.status(jobId);
        take(fresh);
        if (fresh.done) clearInterval(timer);
      } catch (e) {
        setError(describeError(e));
        clearInterval(timer);
      }
    }, POLL_MS);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, status.done]);

  // Load the records of skipped pages once their item has finished.
  const reviewable = status.done && !status.paused;
  const withSkips = status.items.filter((i) => i.status === "ok" && i.pages_skipped.length > 0);
  const wanted = withSkips.map((i) => `${i.item_id}:${i.pages_skipped.length}`).join("|");
  useEffect(() => {
    if (!reviewable) return;
    let live = true;
    (async () => {
      const next: Record<string, PageRecord[]> = {};
      for (const item of withSkips) {
        try {
          const got = await api.job.item(jobId, item.item_id);
          next[item.item_id] = got.pages.filter((p) => p.skipped);
        } catch (e) {
          if (live) setError(describeError(e));
        }
      }
      if (live) setSkippedPages(next);
    })();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, reviewable, wanted]);

  async function cancel() {
    try {
      take(await api.job.cancel(jobId));
    } catch (e) {
      setError(describeError(e));
    }
  }

  /** Resume with the settings as they are NOW -- the pause was most often a
   *  key or a model fixed in Settings since. */
  async function resume() {
    setResuming(true);
    setError("");
    try {
      const settings = loadSettings();
      take(await api.job.resume(jobId, providerConfigured(settings) ? settings : undefined));
    } catch (e) {
      setError(describeError(e));
    } finally {
      setResuming(false);
    }
  }

  async function open(itemId: string, ordinal?: number, manual = false) {
    setError("");
    try {
      await onOpenItem(itemId, ordinal, manual);
    } catch (e) {
      setError(describeError(e));
    }
  }

  /** After a retry: the fixed pages leave the panel, and the counts refresh. */
  async function retried(itemId: string, results: (PageRecord | StillSkipped)[]) {
    const left = mergeRetried(skippedRef.current[itemId] ?? [], results).filter((p) => p.skipped);
    setSkippedPages((prev) => ({ ...prev, [itemId]: left }));
    if (left.length === 0) setCleared((prev) => (prev.includes(itemId) ? prev : [...prev, itemId]));
    try {
      take(await api.job.status(jobId));
    } catch (e) {
      setError(describeError(e));
    }
  }

  const total = status.items.length;
  const finished =
    status.ok + status.skipped + status.failed + status.cancelled_items + status.paused_items;
  const counted = status.items.filter((i) => i.pages_total);
  const pagesTotal = counted.reduce((n, i) => n + (i.pages_total ?? 0), 0);
  const pagesDone = counted.reduce((n, i) => n + Math.min(i.pages_done, i.pages_total ?? 0), 0);
  const translated = status.items.reduce(
    (n, i) => n + Math.max(0, (i.status === "ok" ? i.pages : i.pages_done) - i.pages_skipped.length),
    0,
  );
  const summaryTitle = status.cancelled
    ? "Stopped"
    : `Finished${meta.finished ? ` in ${duration(meta.finished - meta.started - (meta.pausedMs ?? 0))}` : ""}`;
  const summaryLine = [
    `${translated} ${translated === 1 ? "page" : "pages"} translated${status.cancelled ? " before you cancelled" : ""}`,
    status.pages_skipped > 0 && `${status.pages_skipped} not translated, listed below`,
    status.failed > 0 && `${status.failed} failed`,
  ]
    .filter(Boolean)
    .join(" · ");
  const state = status.paused
    ? status.done
      ? "paused"
      : "pausing"
    : status.done
      ? "done"
      : status.cancelled
        ? "cancelling"
        : "running";
  const started = new Date(meta.started).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="view stack">
      <div className="view-head">
        <div>
          <h1>{meta.title}</h1>
          <p className="sub">
            {label(SOURCES, meta.source)} → {label(TARGETS, meta.lang)} · started {started} ·{" "}
            <span className="mono">{displayPath(meta.dest)}</span>
          </p>
        </div>
        <div className="row">
          {state === "running" && (
            <span className="pill running">
              <Icon name="loader" size={12} />
              {status.running} running
            </span>
          )}
          {state === "cancelling" && (
            <span className="pill skipped">
              <Icon name="loader" size={12} />
              Cancelling…
            </span>
          )}
          {(state === "paused" || state === "pausing") && (
            <span className="pill skipped">
              <Icon name={state === "paused" ? "pause" : "loader"} size={12} />
              {state === "paused" ? "Paused" : "Pausing…"}
            </span>
          )}
          {state === "done" && (
            <span className="pill ok">
              <Icon name="check" size={12} />
              Done
            </span>
          )}
          {(!status.done || state === "paused") && (
            <button className="btn danger sm" onClick={cancel} disabled={status.cancelled}>
              <Icon name="x" size={14} />
              Cancel remaining
            </button>
          )}
        </div>
      </div>

      <ErrorAlert error={error} />
      {/* Mounted from the start, so the finish is announced: a live region
          that arrives already filled is often not read out. */}
      <p className="sr-only" role="status">
        {state === "done" ? `${summaryTitle}. ${summaryLine}` : ""}
      </p>
      {state === "done" && (
        <section className="card summary">
          <span className={`icon-tile ${status.cancelled ? "warn" : "ok"}`}>
            <Icon name={status.cancelled ? "alert-circle" : "check-circle"} />
          </span>
          <div>
            <h2>{summaryTitle}</h2>
            <p className="sub">{summaryLine}</p>
          </div>
          <span className="spacer" />
          <button type="button" className="btn" onClick={reveal}>
            <Icon name="folder-open" />
            Show in folder
          </button>
        </section>
      )}
      {status.paused && (
        <Alert tone="warn" title={state === "paused" ? "The run is paused" : "Pausing…"}>
          {status.pause_reason}
          {state === "paused" && (
            <span className="row" style={{ marginTop: 8 }}>
              {/* Disabled until a model is set: the sidecar answers 400 for a
                  resume without settings, rather than run the placeholder. */}
              <button
                type="button"
                className="btn primary sm"
                onClick={resume}
                disabled={resuming || !providerConfigured()}
                title={providerConfigured() ? undefined : "Set up a model in Settings first"}
              >
                <Icon name={resuming ? "loader" : "play"} size={14} className={resuming ? "spin" : undefined} />
                {resuming ? "Resuming…" : "Resume"}
              </button>
              <button type="button" className="btn sm" onClick={onOpenSettings}>
                <Icon name="sliders" size={14} />
                Open Settings
              </button>
            </span>
          )}
        </Alert>
      )}
      {status.warnings.map((w) => (
        <Alert key={w} tone="warn">
          {w}
        </Alert>
      ))}

      <section className="card stack">
        <ProgressBar
          label={pagesTotal ? "Pages finished" : "Chapters finished"}
          value={pagesTotal ? pagesDone : finished}
          max={pagesTotal || total}
          indeterminate={!status.done && pagesTotal === 0 && finished === 0}
          showValue
        />
        <div className="stats stagger">
          <div className="stat" style={{ "--i": 0 } as CSSProperties}>
            <div className="k">Chapters</div>
            <div className="v">
              {finished}
              <span className="faint" style={{ fontSize: "0.9rem" }}>
                {" "}
                / {total}
              </span>
            </div>
          </div>
          <div className="stat ok" style={{ "--i": 1 } as CSSProperties}>
            <div className="k">Pages translated</div>
            <div className="v">{translated}</div>
          </div>
          <div className="stat skipped" style={{ "--i": 2 } as CSSProperties}>
            <div className="k">Pages not translated</div>
            <div className="v">{status.pages_skipped}</div>
          </div>
          <div className="stat failed" style={{ "--i": 3 } as CSSProperties}>
            <div className="k">Failed</div>
            <div className="v">{status.failed}</div>
          </div>
        </div>
      </section>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Chapter</th>
              <th>Pages</th>
              <th>Status</th>
              <th>Notes</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody className="stagger">
            {status.items.map((item, i) => {
              const running = item.status === "pending" && runningItems.has(item.item_id);
              const skippedN = item.pages_skipped.length;
              return (
                <tr key={item.item_id} className={item.status} style={{ "--i": i } as CSSProperties}>
                  <td className="id">
                    <span className="item-name">
                      <Icon name={KIND_ICON[item.kind] ?? "file"} size={14} />
                      {item.item_id}
                    </span>
                  </td>
                  <td className="pages-cell">
                    {running && item.pages_total ? (
                      <ProgressBar
                        label={`${item.item_id} pages`}
                        value={item.pages_done}
                        max={item.pages_total}
                        size="sm"
                      />
                    ) : null}
                    <span className="num">
                      {running
                        ? item.pages_total
                          ? `${item.pages_done} / ${item.pages_total}`
                          : `${item.pages_done}`
                        : item.pages || ""}
                    </span>
                  </td>
                  <td>
                    <StatusPill status={item.status} running={running} />
                  </td>
                  <td className="reason">
                    {item.reason || item.warning}
                    {skippedN > 0 && (
                      <span className="skip-note">
                        <Icon name="skip-forward" size={12} />
                        {skippedN} not translated: page {item.pages_skipped.map((p) => p.ordinal).join(", ")}
                      </span>
                    )}
                  </td>
                  <td className="actions">
                    {item.status === "ok" && skippedN > 0 && reviewable && (
                      <button
                        type="button"
                        className="btn sm"
                        onClick={() => {
                          const panel = document.getElementById(`attention-${item.item_id}`);
                          panel?.scrollIntoView({ block: "start" });
                          panel?.querySelector<HTMLElement>("h2")?.focus();
                        }}
                      >
                        <Icon name="alert-triangle" size={14} />
                        Review
                      </button>
                    )}
                    {item.status === "ok" && (
                      <button type="button" className="btn sm" onClick={() => open(item.item_id)}>
                        <Icon name="pencil" size={14} />
                        Open
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {status.items.length === 0 && (
              <tr>
                <td colSpan={5} className="faint" style={{ textAlign: "center" }}>
                  Nothing in what was added could be translated.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {status.pages_skipped > 0 && status.paused && (
        <p className="faint small">
          Resume or cancel the run to retry the pages that were not translated.
        </p>
      )}
      {cleared.map((id, n) => (
        <Alert key={`cleared-${id}`} tone="success" title={`${id}: every page is translated now`}>
          <span className="row" style={{ marginTop: 6 }}>
            <button
              type="button"
              className="btn sm"
              onClick={() => open(id)}
              ref={n === cleared.length - 1 ? clearedFocus : undefined}
            >
              <Icon name="pencil" size={14} />
              Open in the Editor
            </button>
            <button
              type="button"
              className="btn ghost sm"
              onClick={() => setCleared((prev) => prev.filter((x) => x !== id))}
            >
              Dismiss
            </button>
          </span>
        </Alert>
      ))}
      {reviewable &&
        withSkips.map((item) => {
          const pages = skippedPages[item.item_id];
          if (!pages || pages.length === 0) return null;
          return (
            <NeedsAttention
              key={item.item_id}
              jobId={jobId}
              itemId={item.item_id}
              itemName={withSkips.length > 1 ? item.item_id : undefined}
              pages={pages}
              lang={meta.lang}
              destDir={meta.dest}
              onRetried={(results) => retried(item.item_id, results)}
              onTranslateMyself={(ordinal) => open(item.item_id, ordinal, true)}
            />
          );
        })}
    </div>
  );
}
