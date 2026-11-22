/**
 * The front door: chapters in, one queue out (plan Phase 3.1).
 *
 * Files and folders are dropped or added; every run goes through the queue,
 * so the same Cancel, the same per-page progress, the same review of pages
 * that could not be translated, and the Editor for any item. The sidecar
 * turns what was added into items by the user's folder rule: an archive or
 * PDF is one chapter, the loose images of a folder are one chapter, and each
 * subfolder of images is one more.
 *
 * Input first, then where it goes and which way it is read, then the button.
 * Dragging is never the only way in (WCAG 2.2 dragging): Add files and Add
 * folder do the same through the native dialog.
 *
 * The form lives in App, so a visit to Settings does not empty the list.
 */

import { useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { Alert } from "../components/Alert";
import { Icon } from "../components/Icon";
import { PathField } from "../components/PathField";
import { SOURCES, TARGETS, displayPath, type Source, type Target } from "../lib/api";

export interface TranslateForm {
  /** Files and folders, in the order they were added. */
  paths: string[];
  dest: string;
  source: Source;
  lang: Target;
}

export function basename(p: string): string {
  return p.split(/[\\/]/).filter(Boolean).pop() ?? p;
}

function parent(p: string): string {
  const parts = p.split(/[\\/]/).filter(Boolean);
  parts.pop();
  return parts.join("\\");
}

const CHAPTER_EXTENSIONS = [
  "cbz", "cbr", "cb7", "cbt", "zip", "7z", "rar", "tar", "pdf",
  "png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff",
];
const IMAGE_EXT = /\.(png|jpe?g|webp|bmp|tiff?)$/i;
const DOC_EXT = /\.(pdf)$/i;
const ARCHIVE_EXT = /\.(cb[zr7t]|zip|7z|rar|tar)$/i;

/** What an added path looks like it is. The sidecar decides for real. */
function kindOf(p: string): { icon: "folder" | "book" | "image" | "file"; word: string } {
  if (ARCHIVE_EXT.test(p)) return { icon: "book", word: "archive" };
  if (DOC_EXT.test(p)) return { icon: "file", word: "PDF" };
  if (IMAGE_EXT.test(p)) return { icon: "image", word: "image" };
  return { icon: "folder", word: "folder" };
}

export default function Translate({
  form,
  onForm,
  onAddPaths,
  busy,
  sidecarReady,
  configured,
  onOpenSettings,
  onRun,
  error,
}: {
  form: TranslateForm;
  onForm: (patch: Partial<TranslateForm>) => void;
  /** Appends, de-duplicated, against the CURRENT list (drops arrive late). */
  onAddPaths: (paths: string[]) => void;
  busy: boolean;
  sidecarReady: boolean;
  /** A base URL and a model are set. Without them nothing may run: the
   *  sidecar's offline path would type "HELLO" into every bubble. */
  configured: boolean;
  onOpenSettings: () => void;
  onRun: () => void;
  error: string;
}) {
  const [over, setOver] = useState(false);
  const [note, setNote] = useState("");
  // Read by the drop listener, which is registered once: a drop while a run
  // is starting is ignored, as the buttons are disabled then.
  const busyRef = useRef(busy);
  busyRef.current = busy;

  // Native drops: the webview reports the dropped paths, which a browser's
  // own drag events never expose. In the browser preview there is no
  // webview and the buttons are the way in.
  useEffect(() => {
    let off: (() => void) | undefined;
    let live = true;
    (async () => {
      try {
        const { getCurrentWebview } = await import("@tauri-apps/api/webview");
        const un = await getCurrentWebview().onDragDropEvent((e) => {
          const p = e.payload;
          if (p.type === "enter" || p.type === "over") setOver(true);
          else if (p.type === "drop") {
            setOver(false);
            if (p.paths.length && !busyRef.current) onAddPaths(p.paths);
          } else setOver(false);
        });
        if (live) off = un;
        else un();
      } catch {
        // No webview to listen on: Add files and Add folder still work.
      }
    })();
    return () => {
      live = false;
      off?.();
    };
  }, [onAddPaths]);

  async function pick(directory: boolean) {
    setNote("");
    try {
      const picked = await open({
        title: directory ? "Add folders" : "Add chapters",
        directory,
        multiple: true,
        filters: directory ? undefined : [{ name: "Chapters and pages", extensions: CHAPTER_EXTENSIONS }],
      });
      const list = Array.isArray(picked) ? picked : typeof picked === "string" ? [picked] : [];
      if (list.length) onAddPaths(list);
    } catch (e) {
      setNote(String(e));
    }
  }

  const locked = busy || !sidecarReady || !configured;
  const canRun = !locked && form.paths.length > 0 && form.dest.trim() !== "";
  const n = form.paths.length;

  return (
    <div className="view stack">
      <div className="view-head">
        <div>
          <h1>Translate</h1>
          <p className="sub">
            Add chapters or whole folders. Pages come out typeset in the target language.
          </p>
        </div>
      </div>

      {!configured && (
        <Alert tone="warn" title="Set up a model first">
          Translating needs an endpoint and a model.{" "}
          <button type="button" className="btn sm" onClick={onOpenSettings}>
            <Icon name="sliders" size={14} />
            Open Settings
          </button>
        </Alert>
      )}
      {error && <Alert tone="error">{error}</Alert>}

      <section className="card stack" aria-busy={busy}>
        <div className="card-head" style={{ marginBottom: 0 }}>
          <span className="icon-tile">
            <Icon name="book" />
          </span>
          <div>
            <h2>Chapters</h2>
            <p className="sub">
              Archives (.cbz, .cbr, .cb7) and PDFs are one chapter each; a folder of images is one
              chapter, and so is each subfolder of images.
            </p>
          </div>
        </div>

        <div className={`dropzone${over ? " over" : ""}`}>
          <Icon name="folder-open" size={28} />
          <p>
            <strong>Drop files or folders here</strong>
            <span className="faint"> — or</span>
          </p>
          <div className="row">
            <button type="button" className="btn" onClick={() => pick(false)} disabled={busy}>
              <Icon name="file" />
              Add files
            </button>
            <button type="button" className="btn" onClick={() => pick(true)} disabled={busy}>
              <Icon name="folder" />
              Add folder
            </button>
          </div>
          {note && <p className="hint">{note}</p>}
        </div>

        {n > 0 && (
          <>
            <ul className="input-list" aria-label="Added chapters">
              {form.paths.map((p) => {
                const k = kindOf(p);
                return (
                  <li key={p}>
                    <Icon name={k.icon} size={16} />
                    <span className="name">{basename(p)}</span>
                    <span className="where mono faint">{displayPath(parent(p))}</span>
                    <span className="kind faint">{k.word}</span>
                    <button
                      type="button"
                      className="btn icon sm ghost"
                      onClick={() => onForm({ paths: form.paths.filter((x) => x !== p) })}
                      disabled={busy}
                    >
                      <Icon name="x" size={14} label={`Remove ${basename(p)}`} />
                    </button>
                  </li>
                );
              })}
            </ul>
            <div className="row between">
              <span className="muted small">
                {n} {n === 1 ? "entry" : "entries"} added
              </span>
              <button type="button" className="btn ghost sm" onClick={() => onForm({ paths: [] })} disabled={busy}>
                Clear list
              </button>
            </div>
          </>
        )}
      </section>

      <section className="card stack" aria-busy={busy}>
        <div className="card-head" style={{ marginBottom: 0 }}>
          <span className="icon-tile">
            <Icon name="languages" />
          </span>
          <div>
            <h2>Languages and output</h2>
            <p className="sub">Which way the pages are read, and where they go.</p>
          </div>
        </div>
        <div className="row">
          <div className="field" style={{ flex: 1, minWidth: 160 }}>
            <label className="label" htmlFor="source-lang">
              From
            </label>
            <select
              id="source-lang"
              value={form.source}
              onChange={(e) => onForm({ source: e.target.value as Source })}
              disabled={busy}
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
              To
            </label>
            <select
              id="target-lang"
              value={form.lang}
              onChange={(e) => onForm({ lang: e.target.value as Target })}
              disabled={busy}
            >
              {TARGETS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <PathField
          id="dest"
          label="Output folder"
          hint="Each chapter gets its own subfolder here."
          mode="directory"
          value={form.dest}
          onChange={(dest) => onForm({ dest })}
          placeholder="C:\Manga\translated"
          disabled={busy}
        />
      </section>

      <div className="row end">
        {!sidecarReady && <span className="faint small">Buttons unlock once the sidecar answers.</span>}
        {sidecarReady && configured && n > 0 && !form.dest.trim() && (
          <span className="faint small">Pick an output folder to start.</span>
        )}
        <button className="btn primary" onClick={onRun} disabled={!canRun}>
          {busy ? <Icon name="loader" className="spin" /> : <Icon name="play" />}
          {busy ? "Starting…" : n > 1 ? `Translate ${n} entries` : "Translate"}
        </button>
      </div>
    </div>
  );
}
