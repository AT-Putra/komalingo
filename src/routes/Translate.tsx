/**
 * The front door: one chapter or a whole folder, into the pipeline.
 *
 * The form's state lives in App, not here. Switching to Settings and back
 * unmounts this view, and a form that forgot the paths on every visit would
 * be retyped on every visit. This file owns layout and the working panel.
 *
 * The working panel is the single-file flow's progress. The folder flow
 * answers at once and hands off to the Queue view, which polls its own status
 * snapshot; the status bar carries the live stage line for both.
 */

import { Alert } from "../components/Alert";
import { Icon } from "../components/Icon";
import { PathField } from "../components/PathField";
import { ProgressBar, StageTrack } from "../components/Progress";
import { SOURCES, TARGETS, type Progress, type Source, type Target } from "../lib/api";

export interface TranslateForm {
  src: string;
  folder: string;
  dest: string;
  source: Source;
  lang: Target;
}

export type Busy = "" | "item" | "folder";

export function basename(p: string): string {
  return p.split(/[\\/]/).filter(Boolean).pop() ?? p;
}

export default function Translate({
  form,
  onForm,
  busy,
  sidecarReady,
  onRunItem,
  onRunFolder,
  error,
  warnings,
  progress,
  pagesDone,
}: {
  form: TranslateForm;
  onForm: (patch: Partial<TranslateForm>) => void;
  busy: Busy;
  sidecarReady: boolean;
  onRunItem: () => void;
  onRunFolder: () => void;
  error: string;
  warnings: string[];
  progress: Progress | null;
  /** `write` lines seen since this run began. The item flow does not know its
   *  page count until it returns, so this is the honest counter. */
  pagesDone: number;
}) {
  const locked = busy !== "" || !sidecarReady;
  const canItem = !locked && form.src.trim() !== "" && form.dest.trim() !== "";
  const canFolder = !locked && form.folder.trim() !== "" && form.dest.trim() !== "";

  return (
    <div className="view stack">
      <div className="view-head">
        <div>
          <h1>Translate</h1>
          <p className="sub">
            One chapter or a whole folder. Pages come out typeset in the target language.
          </p>
        </div>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {warnings.map((w) => (
        <Alert key={w} tone="warn">
          {w}
        </Alert>
      ))}

      {busy === "item" && (
        <section className="card working" aria-live="polite">
          <div className="headline">
            <span className="icon-tile" style={{ color: "var(--accent)" }}>
              <Icon name="loader" className="spin" size={20} />
            </span>
            <div className="what">
              <div className="name">{basename(form.src)}</div>
              <div className="detail">
                {progress && progress.stage !== "item_start"
                  ? `Page ${progress.page} · ${progress.stage} · ${progress.item}`
                  : "Opening the archive…"}
              </div>
            </div>
            <span className="counter">
              <strong>{pagesDone}</strong> {pagesDone === 1 ? "page" : "pages"} written
            </span>
          </div>
          <StageTrack stage={progress?.stage} />
          <ProgressBar
            label="Current page"
            value={progress?.pct ?? 0}
            indeterminate={!progress || progress.stage === "item_start"}
            showValue
          />
        </section>
      )}

      {busy === "folder" && (
        <section className="card working" aria-live="polite">
          <div className="headline">
            <span className="icon-tile" style={{ color: "var(--accent)" }}>
              <Icon name="loader" className="spin" size={20} />
            </span>
            <div className="what">
              <div className="name">{basename(form.folder)}</div>
              <div className="detail">Queueing every file in the folder…</div>
            </div>
          </div>
          <ProgressBar label="Starting the job" value={0} indeterminate />
        </section>
      )}

      <section className="card" aria-busy={busy !== ""}>
        <div className="card-head">
          <span className="icon-tile">
            <Icon name="languages" />
          </span>
          <div>
            <h2>Output</h2>
            <p className="sub">Where the pages go, and which way they are read.</p>
          </div>
        </div>
        <div className="stack">
          <PathField
            id="dest"
            label="Output folder"
            hint="Each item gets its own subfolder here."
            mode="directory"
            value={form.dest}
            onChange={(dest) => onForm({ dest })}
            placeholder="C:\Manga\translated"
            disabled={busy !== ""}
          />
          <div className="row">
            <div className="field" style={{ flex: 1, minWidth: 160 }}>
              <label className="label" htmlFor="source-lang">
                Source language
              </label>
              <select
                id="source-lang"
                value={form.source}
                onChange={(e) => onForm({ source: e.target.value as Source })}
                disabled={busy !== ""}
              >
                {SOURCES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <span className="faint" style={{ paddingTop: 22 }} aria-hidden>
              <Icon name="arrow-right" />
            </span>
            <div className="field" style={{ flex: 1, minWidth: 160 }}>
              <label className="label" htmlFor="target-lang">
                Target language
              </label>
              <select
                id="target-lang"
                value={form.lang}
                onChange={(e) => onForm({ lang: e.target.value as Target })}
                disabled={busy !== ""}
              >
                {TARGETS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </section>

      <div className="grid-2">
        <section className="card stack" aria-busy={busy !== ""}>
          <div className="card-head" style={{ marginBottom: 0 }}>
            <span className="icon-tile">
              <Icon name="book" />
            </span>
            <div>
              <h2>One chapter</h2>
              <p className="sub">A .cbz or .pdf, every page, then straight into the editor.</p>
            </div>
          </div>
          <PathField
            id="src"
            label="Archive"
            mode="file"
            filters={[{ name: "Comic archive or PDF", extensions: ["cbz", "pdf", "zip"] }]}
            value={form.src}
            onChange={(src) => onForm({ src })}
            placeholder="C:\Manga\chapter-01.cbz"
            disabled={busy !== ""}
          />
          <div className="row end">
            <button className="btn primary" onClick={onRunItem} disabled={!canItem}>
              {busy === "item" ? <Icon name="loader" className="spin" /> : <Icon name="play" />}
              {busy === "item" ? "Translating…" : "Translate chapter"}
            </button>
          </div>
        </section>

        <section className="card stack" aria-busy={busy !== ""}>
          <div className="card-head" style={{ marginBottom: 0 }}>
            <span className="icon-tile">
              <Icon name="folder" />
            </span>
            <div>
              <h2>Whole folder</h2>
              <p className="sub">Images, PDFs and archives, queued and run in parallel.</p>
            </div>
          </div>
          <PathField
            id="folder"
            label="Folder"
            mode="directory"
            value={form.folder}
            onChange={(folder) => onForm({ folder })}
            placeholder="C:\Manga\series"
            disabled={busy !== ""}
          />
          <div className="row end">
            <button className="btn primary" onClick={onRunFolder} disabled={!canFolder}>
              {busy === "folder" ? <Icon name="loader" className="spin" /> : <Icon name="list" />}
              {busy === "folder" ? "Queueing…" : "Translate folder"}
            </button>
          </div>
        </section>
      </div>

      {!sidecarReady && busy === "" && (
        <p className="faint small">Buttons unlock once the sidecar answers.</p>
      )}
    </div>
  );
}
