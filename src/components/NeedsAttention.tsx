/**
 * The pages a run could not translate, and the four ways to try again
 * (plan Phase 3.3). Used twice: in the Queue for every skipped page of an
 * item, and in the Editor for the one page on screen (`compact`).
 *
 * A retry runs on the sidecar in the background; this polls its status and
 * hands every page that came back to `onRetried`, so the parent can swap the
 * fixed records in and the panel shrinks to what is still not translated.
 * The retry belongs to the sidecar, not to this panel: a panel mounted while
 * one is running (the user moved to another page and back, or opened the
 * Editor from the Queue) picks it up again from GET /api/pages/retry, so a
 * page fixed while nobody was watching does not go on saying it was not.
 *
 * The four ways, in the order a refusal is most often got past:
 *   - without the image: the OCR text alone. The artwork is what most
 *     refusals react to. Cost: the model can no longer tell lettering from
 *     art, so the page is worth a look afterwards (the hint says so).
 *   - another model, picked from the same endpoint's list.
 *   - translate it myself: the Editor's hand mode, one page at a time.
 *   - as-is: the same request again, for a timeout or an outage.
 */

import { useEffect, useId, useRef, useState } from "react";
import { Alert } from "./Alert";
import { ErrorAlert } from "./ErrorAlert";
import { Icon } from "./Icon";
import { ModelCombobox, type ModelComboboxHandle } from "./ModelCombobox";
import { ProgressBar } from "./Progress";
import {
  api,
  describeError,
  isFixed,
  loadSettings,
  providerConfigured,
  type ModelInfo,
  type PageRecord,
  type RetryMode,
  type RetryStatus,
  type StillSkipped,
  type Target,
} from "../lib/api";
import { pageUrl } from "../lib/pageUrl";

const POLL_MS = 500;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** What the last retry did to one page, shown on its card. */
type Outcome = { tone: "ok" | "still"; text: string };

/**
 * An item's page records after a retry: a fixed page's fresh record replaces
 * it; a page still not translated keeps its record with the new reason.
 */
export function mergeRetried(
  pages: PageRecord[],
  results: (PageRecord | StillSkipped)[],
): PageRecord[] {
  const by = new Map(results.map((r) => [r.page, r]));
  return pages.map((p) => {
    const r = by.get(p.page);
    if (!r) return p;
    return isFixed(r) ? r : { ...p, skipped: r.skipped };
  });
}

const MODE_WORDS: Record<RetryMode, string> = {
  text_only: "without the image",
  model: "with another model",
  same: "as-is",
};

export function NeedsAttention({
  jobId,
  itemId,
  itemName,
  pages,
  lang,
  destDir,
  compact = false,
  blocked = "",
  onRetried,
  onTranslateMyself,
}: {
  jobId: string;
  itemId: string;
  /** Shown in the heading when the Queue lists several items. */
  itemName?: string;
  /** The item's SKIPPED page records. */
  pages: PageRecord[];
  lang: Target;
  destDir: string;
  /** One page in the Editor: no checkboxes, no thumbnail. */
  compact?: boolean;
  /** Why the sidecar would refuse a retry now (the job still runs, or is
   *  paused); the actions are disabled and this says why. */
  blocked?: string;
  onRetried: (pages: (PageRecord | StillSkipped)[]) => void;
  onTranslateMyself: (ordinal: number) => void;
}) {
  const uid = useId();
  const titleId = `${uid}-title`;
  const hintId = `${uid}-hint`;
  const modelId = `${uid}-model`;
  const [selected, setSelected] = useState<Set<number>>(() => new Set(pages.map((p) => p.page)));
  const [busy, setBusy] = useState<RetryMode | "">("");
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [outcomes, setOutcomes] = useState<Record<number, Outcome>>({});
  const [error, setError] = useState("");
  const [fixedNote, setFixedNote] = useState("");
  const [picking, setPicking] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [model, setModel] = useState("");
  const [loadingModels, setLoadingModels] = useState(false);
  const box = useRef<ModelComboboxHandle>(null);
  const live = useRef(true);

  // A retry already running for this item -- started before this panel
  // mounted -- is followed; one that finished unseen is applied.
  useEffect(() => {
    live.current = true;
    (async () => {
      try {
        const st = await api.pages.retryStatus(jobId, itemId);
        if (!live.current) return;
        const mine = new Set(pages.map((p) => p.page));
        if (st.status === "running") await follow(st);
        else if (st.pages.some((p) => mine.has(p.page))) finish(st);
      } catch {
        // 404: nothing was ever retried for this item.
      }
    })();
    return () => {
      live.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, itemId]);

  // Pages that left the list (fixed) leave the selection too; new ones join.
  useEffect(() => {
    setSelected((prev) => {
      const ids = new Set(pages.map((p) => p.page));
      const next = new Set([...prev].filter((n) => ids.has(n)));
      for (const n of ids) if (!prev.has(n) && !(n in outcomes)) next.add(n);
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pages]);

  const configured = providerConfigured();
  const chosen = compact ? pages.map((p) => p.page) : [...selected];
  const canRetry = configured && !blocked && busy === "" && chosen.length > 0;

  /** Report what a finished retry did, and hand its pages up. */
  function finish(st: RetryStatus) {
    const next: Record<number, Outcome> = {};
    let fixed = 0;
    for (const p of st.pages) {
      if (isFixed(p)) {
        fixed++;
        next[p.page] = { tone: "ok", text: `Translated ${MODE_WORDS[st.mode]}.` };
      } else {
        next[p.page] = { tone: "still", text: `Still not translated: ${p.skipped.message}` };
      }
    }
    setOutcomes((prev) => ({ ...prev, ...next }));
    if (fixed) {
      setFixedNote(`${fixed} ${fixed === 1 ? "page" : "pages"} translated ${MODE_WORDS[st.mode]}.`);
    }
    if (st.status === "failed") {
      setError(
        st.kind === "account"
          ? `The provider refused the account, so nothing was retried: ${st.error}`
          : st.error,
      );
    }
    onRetried(st.pages);
  }

  /** Poll a running retry to its end. */
  async function follow(first: RetryStatus) {
    let st = first;
    setBusy(st.mode);
    setProgress({ done: st.done, total: st.total });
    try {
      while (st.status === "running" && live.current) {
        await sleep(POLL_MS);
        st = await api.pages.retryStatus(jobId, itemId);
        if (live.current) setProgress({ done: st.done, total: st.total });
      }
      if (live.current) finish(st);
    } finally {
      if (live.current) setBusy("");
    }
  }

  async function retry(mode: RetryMode, otherModel?: string) {
    const settings = loadSettings();
    if (!providerConfigured(settings)) {
      setError("Set up a model in Settings first.");
      return;
    }
    setError("");
    setFixedNote("");
    try {
      const st = await api.pages.retry({
        job_id: jobId,
        item_id: itemId,
        ordinals: chosen,
        dest_dir: destDir,
        lang,
        mode,
        model: otherModel,
        settings,
      });
      await follow(st);
    } catch (e) {
      if (live.current) {
        setError(describeError(e));
        setBusy("");
      }
    }
  }

  async function togglePicker() {
    if (picking) {
      setPicking(false);
      return;
    }
    setPicking(true);
    if (models.length || loadingModels) {
      box.current?.open();
      return;
    }
    setLoadingModels(true);
    try {
      const s = loadSettings();
      const r = await api.models({ base_url: s.base_url, api_key: s.api_key });
      if (!live.current) return;
      setModels(r.models.filter((m) => m.id !== s.model));
      box.current?.open();
    } catch (e) {
      if (live.current) setError(describeError(e));
    } finally {
      if (live.current) setLoadingModels(false);
    }
  }

  function toggle(n: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });
  }

  const all = pages.length > 0 && pages.every((p) => selected.has(p.page));

  return (
    <section
      className={`card stack attention${compact ? " compact" : ""}`}
      aria-labelledby={titleId}
      id={`attention-${itemId}`}
    >
      <div className="card-head" style={{ marginBottom: 0 }}>
        <span className="icon-tile warn">
          <Icon name="alert-triangle" />
        </span>
        <div>
          {/* tabIndex -1: the Queue's Review button moves focus here. */}
          <h2 id={titleId} tabIndex={-1}>
            {compact ? "Not translated" : "Needs attention"}
            {itemName ? <span className="faint"> · {itemName}</span> : null}
          </h2>
          <p className="sub">
            {compact
              ? "Try it again another way, or type it yourself."
              : `${pages.length} ${pages.length === 1 ? "page was" : "pages were"} not translated. The originals are in their slots.`}
          </p>
        </div>
      </div>

      {!compact && pages.length > 1 && (
        <label className="check-row">
          <input
            type="checkbox"
            checked={all}
            onChange={() => setSelected(all ? new Set() : new Set(pages.map((p) => p.page)))}
            disabled={busy !== ""}
          />
          Select all
        </label>
      )}

      {!compact && (
        <ul className="attention-list">
          {pages.map((p) => {
            const out = outcomes[p.page];
            return (
              <li key={p.page} className={`attention-page${out ? ` ${out.tone}` : ""}`}>
                <input
                  type="checkbox"
                  checked={selected.has(p.page)}
                  onChange={() => toggle(p.page)}
                  disabled={busy !== ""}
                  aria-label={`Select page ${p.page}`}
                />
                <img
                  className="thumb"
                  src={pageUrl(p.output)}
                  alt={`Page ${p.page}, as drawn`}
                  loading="lazy"
                />
                <div className="what">
                  <div className="title">
                    Page {p.page}
                    {p.member && <span className="mono faint"> · {p.member}</span>}
                  </div>
                  <div className="msg">{out ? out.text : p.skipped?.message}</div>
                  {p.skipped?.detail && (
                    <details>
                      <summary>Details from the provider</summary>
                      <code className="alert-path">{p.skipped.detail}</code>
                    </details>
                  )}
                </div>
                <button
                  type="button"
                  className="btn sm"
                  onClick={() => onTranslateMyself(p.page)}
                  disabled={busy !== "" || !!blocked}
                >
                  <Icon name="pencil" size={14} />
                  Translate myself
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {compact && outcomes[pages[0]?.page] && (
        <p className={`attention-outcome ${outcomes[pages[0].page].tone}`} role="status">
          {outcomes[pages[0].page].text}
        </p>
      )}

      <div className="attention-actions">
        {!compact && (
          <span className="muted small">
            {chosen.length} of {pages.length} selected
          </span>
        )}
        <span className="spacer" />
        <button
          type="button"
          className="btn primary sm"
          onClick={() => retry("text_only")}
          disabled={!canRetry}
          aria-describedby={hintId}
        >
          <Icon
            name={busy === "text_only" ? "loader" : "image"}
            size={14}
            className={busy === "text_only" ? "spin" : undefined}
          />
          Retry without image
        </button>
        <button
          type="button"
          className="btn sm"
          onClick={togglePicker}
          disabled={!canRetry && !picking}
          aria-expanded={picking}
          aria-controls={picking ? `${uid}-picker` : undefined}
        >
          <Icon name="sliders" size={14} />
          Another model…
        </button>
        {compact && (
          <button
            type="button"
            className="btn sm"
            onClick={() => onTranslateMyself(pages[0].page)}
            disabled={busy !== "" || !!blocked}
          >
            <Icon name="pencil" size={14} />
            Translate myself
          </button>
        )}
        <button
          type="button"
          className="btn ghost sm"
          onClick={() => retry("same")}
          disabled={!canRetry}
          aria-describedby={hintId}
        >
          <Icon
            name={busy === "same" ? "loader" : "refresh"}
            size={14}
            className={busy === "same" ? "spin" : undefined}
          />
          Retry as-is
        </button>
      </div>

      {picking && (
        <div className="attention-picker" id={`${uid}-picker`}>
          <label className="sr-only" htmlFor={modelId}>
            Model to retry with
          </label>
          <div className="control">
            <ModelCombobox
              ref={box}
              id={modelId}
              value={model}
              onChange={setModel}
              options={models}
              placeholder={loadingModels ? "Loading models…" : "type or pick a model"}
              disabled={busy !== ""}
            />
            <button
              type="button"
              className="btn primary"
              onClick={() => retry("model", model.trim())}
              disabled={!canRetry || !model.trim()}
            >
              <Icon
                name={busy === "model" ? "loader" : "play"}
                size={14}
                className={busy === "model" ? "spin" : undefined}
              />
              Retry with this model
            </button>
          </div>
        </div>
      )}

      <p id={hintId} className="hint">
        {blocked
          ? blocked
          : configured
            ? "Without the image the model cannot see the art, so check those pages for artwork erased as text. Retry as-is is for a timeout or a busy provider."
            : "Set up a model in Settings to retry."}
      </p>

      {busy !== "" && (
        <ProgressBar
          label={`Retrying ${MODE_WORDS[busy]}`}
          value={progress.done}
          max={Math.max(progress.total, 1)}
          showValue
        />
      )}
      {fixedNote && <Alert tone="success">{fixedNote}</Alert>}
      <ErrorAlert error={error} />
    </section>
  );
}
