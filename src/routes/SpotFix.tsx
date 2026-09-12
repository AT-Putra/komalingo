/**
 * AC-10's editor: click a bubble, edit the translation, re-render that page.
 *
 * Two things here are load-bearing and easy to get subtly wrong.
 *
 * **Hit-testing happens in PAGE coordinates.** The canvas is displayed at
 * whatever width the window allows, and the polygons in regions.json are in
 * the page raster's own pixels. Testing the click where it landed on screen
 * works at exactly one zoom level and silently mis-selects at every other, so
 * the display scale is divided out before the point-in-polygon test rather
 * than after. The test is even-odd ray casting, which is what the typesetter
 * uses to decide what is inside a bubble -- a UI that disagreed with the engine
 * about the inside of a concave bubble would select one region and edit another.
 *
 * **`fit_compromised` and `fit_failed` come from the server on every render and
 * are never held.** They are recomputed by the typesetter from the geometry,
 * so shortening an edit clears them; a component that kept its own copy would
 * keep a bubble highlighted after the user had already fixed it. The list
 * order is the job summary's, because that summary is what AC-1 exists to
 * make trustworthy.
 */

import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Alert } from "../components/Alert";
import { Icon } from "../components/Icon";
import {
  api,
  describeError,
  loadSettings,
  type PageRecord,
  type Region,
  type Target,
} from "../lib/api";

/** Even-odd ray casting, in page coordinates. */
/** Where the English is: the room when the typesetter found one, else the block. */
function laidInto(r: Region): [number, number][] {
  return r.room && r.room.length >= 3 ? r.room : r.polygon;
}

function inPolygon(x: number, y: number, poly: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/** Failed first, then compromised, then the rest -- the order the plan asks for. */
function severity(r: Region): number {
  if (r.fit_failed) return 0;
  if (r.fit_compromised) return 1;
  return 2;
}

export default function SpotFix({
  job,
  page,
  pages,
  onSelectPage,
  destDir,
  lang,
  onPage,
}: {
  job: string;
  page: PageRecord;
  /** Every page of the item, for the strip. Flags come from each record. */
  pages: PageRecord[];
  onSelectPage: (p: PageRecord) => void;
  destDir: string;
  /** The job's target language. A re-render under another one is a cache
   *  miss by design (the mixed-language guard), so it must be the job's. */
  lang: Target;
  /** Called with the server's fresh record after every successful re-render. */
  onPage: (p: PageRecord) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [landed, setLanded] = useState(false);

  // Sorted for display only. The region objects themselves are the server's.
  const ordered = useMemo(
    () =>
      [...page.regions].sort(
        (a, b) => severity(a) - severity(b) || a.id - b.id,
      ),
    [page.regions],
  );

  // The delivered page, redrawn whenever the server hands back a new one. The
  // cache-buster is the point: the re-render writes to the SAME path, so
  // without it the browser shows the pre-edit image and the user concludes
  // nothing happened.
  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const img = new Image();
    img.onload = () => {
      el.width = img.naturalWidth;
      el.height = img.naturalHeight;
      const ctx = el.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(img, 0, 0);
      for (const r of page.regions) {
        if (!r.fit_failed && !r.fit_compromised && r.id !== selected) continue;
        ctx.beginPath();
        laidInto(r).forEach(([x, y], i) =>
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y),
        );
        ctx.closePath();
        ctx.lineWidth = 3;
        ctx.strokeStyle =
          r.id === selected ? "#2b7" : r.fit_failed ? "#d33" : "#e90";
        ctx.stroke();
      }
    };
    // No cache-buster on a data: URL: a query string would corrupt it, and an
    // inline image cannot be stale anyway.
    const src = convertPath(page.output);
    img.src = src.startsWith("data:") ? src : `${src}?v=${Date.now()}`;
  }, [page, selected]);

  function pick(e: React.MouseEvent<HTMLCanvasElement>) {
    const el = canvas.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    // Divide the display scale out. el.width is the PAGE width; box.width is
    // however many screen pixels it is currently shown in.
    const x = ((e.clientX - box.left) * el.width) / box.width;
    const y = ((e.clientY - box.top) * el.height) / box.height;
    const hit = page.regions.find((r) => inPolygon(x, y, laidInto(r)));
    if (hit) select(hit);
  }

  function select(r: Region) {
    setSelected(r.id);
    setDraft(r.translation);
    setError("");
    setLanded(false);
  }

  useEffect(() => {
    if (!landed) return;
    const t = setTimeout(() => setLanded(false), 2500);
    return () => clearTimeout(t);
  }, [landed]);

  async function confirm() {
    if (selected === null || busy) return;
    setBusy(true);
    setError("");
    try {
      const settings = loadSettings();
      const fresh = await api.rerender({
        job_id: job,
        item_id: page.item_id,
        ordinal: page.page,
        region_id: selected,
        text: draft,
        dest_dir: destDir,
        lang,
        // Sent only when configured. An empty base URL is "not configured
        // yet", and the sidecar answers 400 for it rather than running a
        // silent offline placeholder the user did not ask for.
        settings: settings.base_url && settings.model ? settings : undefined,
      });
      onPage(fresh);
      setLanded(true);
    } catch (e) {
      // describeError, never a synonym: the provider's own status and body
      // reach the user verbatim (AC-8).
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  const current = ordered.find((r) => r.id === selected) ?? null;
  const failed = page.fit_summary.fit_failed.length;
  const tight = page.fit_summary.fit_compromised.length;

  return (
    <div className="view stack">
      <div className="view-head">
        <div>
          <h1>Editor</h1>
          <p className="sub">
            Click a bubble on the page, or pick it from the list, then rewrite it.
          </p>
        </div>
        <div className="row">
          {failed > 0 && (
            <span className="pill failed">
              <Icon name="alert-circle" size={12} />
              {failed} did not fit
            </span>
          )}
          {tight > 0 && (
            <span className="pill skipped">
              <Icon name="alert-triangle" size={12} />
              {tight} tight
            </span>
          )}
          {failed === 0 && tight === 0 && (
            <span className="pill ok">
              <Icon name="check" size={12} />
              Every bubble fits
            </span>
          )}
        </div>
      </div>

      <nav className="page-strip" aria-label="Pages">
        {pages.map((p) => {
          const f = p.fit_summary.fit_failed.length;
          const c = p.fit_summary.fit_compromised.length;
          return (
            <button
              key={p.page}
              type="button"
              className="chip"
              onClick={() => onSelectPage(p)}
              aria-current={p.page === page.page ? "true" : undefined}
              aria-label={`Page ${p.page}${f ? `, ${f} did not fit` : c ? `, ${c} tight` : ""}`}
            >
              {p.page}
              {f > 0 ? <span className="mark" /> : c > 0 ? <span className="mark warn" /> : null}
            </button>
          );
        })}
      </nav>

      {page.cache_warning && <Alert tone="warn">{page.cache_warning}</Alert>}
      {page.edit_on_other_model && (
        <Alert tone="info">
          This page has an edit saved against a different model. It is kept, and it
          is not being used here.
        </Alert>
      )}
      {error && <Alert tone="error">{error}</Alert>}

      <div className="editor-grid">
        <div className="canvas-frame">
          <canvas
            ref={canvas}
            onClick={pick}
            className="page"
            aria-label={`Page ${page.page}, ${page.member}. Click a bubble to select it.`}
          />
          <div className="legend" aria-hidden>
            <span>
              <i style={{ background: "#2b7" }} /> selected
            </span>
            <span>
              <i style={{ background: "#d33" }} /> did not fit
            </span>
            <span>
              <i style={{ background: "#e90" }} /> tight
            </span>
            <span className="spacer" />
            <span className="mono">{page.member}</span>
          </div>
        </div>

        <div className="stack">
          <section className="card">
            <div className="card-head">
              <span className="icon-tile">
                <Icon name="list" />
              </span>
              <div>
                <h2>Bubbles</h2>
                <p className="sub">{page.regions.length} on this page, problems first.</p>
              </div>
            </div>
            <ol className="regions stagger">
              {ordered.map((r, i) => (
                <li key={r.id} style={{ "--i": i } as CSSProperties}>
                  <button
                    type="button"
                    className="region"
                    onClick={() => select(r)}
                    disabled={busy}
                    aria-pressed={r.id === selected}
                  >
                    <span className="top">
                      <span className="id">#{r.id}</span>
                      {r.fit_failed ? (
                        <span className="flag failed">
                          <Icon name="alert-circle" size={12} />
                          did not fit{r.fit_reason ? `: ${r.fit_reason}` : ""}
                        </span>
                      ) : r.fit_compromised ? (
                        <span className="flag compromised">
                          <Icon name="alert-triangle" size={12} />
                          tight
                        </span>
                      ) : null}
                      {r.edited && (
                        <span className="flag edited">
                          <Icon name="pencil" size={12} />
                          edited
                        </span>
                      )}
                    </span>
                    <span className="text">{r.typeset || r.translation}</span>
                  </button>
                </li>
              ))}
              {ordered.length === 0 && (
                <li className="empty">No text was detected on this page.</li>
              )}
            </ol>
          </section>

          {current ? (
            <section className="card stack" key={current.id}>
              <div className="card-head" style={{ marginBottom: 0 }}>
                <span className="icon-tile">
                  <Icon name="pencil" />
                </span>
                <div>
                  <h2>Bubble #{current.id}</h2>
                  <p className="sub">Ctrl+Enter re-renders.</p>
                </div>
              </div>
              {current.text && <div className="source-text">{current.text}</div>}
              <div className="field">
                <label className="label" htmlFor="spotfix-text">
                  Translation
                </label>
                <textarea
                  id="spotfix-text"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault();
                      confirm();
                    }
                  }}
                  rows={4}
                  disabled={busy}
                />
              </div>
              {landed && <Alert tone="success">Re-rendered. The page above is the new one.</Alert>}
              {/* Disabled while a re-render is in flight, so a second confirm
                  cannot race the first: both would write the same output path and
                  the later response would not necessarily be the later write. */}
              <div className="row end">
                <button
                  className="btn primary"
                  onClick={confirm}
                  disabled={busy || draft === current.translation}
                >
                  {busy ? <Icon name="loader" className="spin" /> : <Icon name="refresh" />}
                  {busy ? "Re-rendering…" : "Re-render this page"}
                </button>
              </div>
            </section>
          ) : (
            <section className="card">
              <p className="faint" style={{ textAlign: "center" }}>
                Select a bubble to edit its translation.
              </p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * A local file path as something the webview will load.
 *
 * ponytail: `asset://` via Tauri's convertFileSrc is the supported route and
 * needs the asset protocol enabled in tauri.conf.json, which is a Phase 8
 * packaging change. Ceiling: the canvas stays blank in a packaged build until
 * that scope entry exists. Upgrade path: import convertFileSrc from
 * "@tauri-apps/api/core" here and delete this function.
 */
function convertPath(p: string): string {
  return p.replace(/^\\\\\?\\/, "").replace(/\\/g, "/");
}
