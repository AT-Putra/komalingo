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

import { useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  describeError,
  loadSettings,
  type PageRecord,
  type Region,
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
  destDir,
  onPage,
}: {
  job: string;
  page: PageRecord;
  destDir: string;
  /** Called with the server's fresh record after every successful re-render. */
  onPage: (p: PageRecord) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
    img.src = `${convertPath(page.output)}?v=${Date.now()}`;
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
  }

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
        // Sent only when configured. An empty base URL is "not configured
        // yet", and the sidecar answers 400 for it rather than running a
        // silent offline placeholder the user did not ask for.
        settings: settings.base_url && settings.model ? settings : undefined,
      });
      onPage(fresh);
    } catch (e) {
      // describeError, never a synonym: the provider's own status and body
      // reach the user verbatim (AC-8).
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  const current = ordered.find((r) => r.id === selected) ?? null;

  return (
    <section className="spotfix">
      <h2>
        Page {page.page} — {page.member}
      </h2>

      {page.cache_warning && <p className="warn">{page.cache_warning}</p>}
      {page.edit_on_other_model && (
        <p className="warn">
          This page has an edit saved against a different model. It is kept, and
          it is not being used here.
        </p>
      )}
      {error && <pre className="error">{error}</pre>}

      <canvas ref={canvas} onClick={pick} className="page" />

      <ol className="regions">
        {ordered.map((r) => (
          <li key={r.id}>
            <button
              onClick={() => select(r)}
              disabled={busy}
              className={
                r.fit_failed ? "failed" : r.fit_compromised ? "compromised" : ""
              }
            >
              #{r.id}
              {r.fit_failed
                ? ` — did not fit${r.fit_reason ? `: ${r.fit_reason}` : ""}`
                : r.fit_compromised
                  ? " — tight fit"
                  : ""}
              {r.edited ? " — edited" : ""}
            </button>
            <span className="typeset">{r.typeset || r.translation}</span>
          </li>
        ))}
      </ol>

      {current && (
        <div className="editor">
          <label htmlFor="spotfix-text">Region #{current.id}</label>
          {current.text && <p className="source">{current.text}</p>}
          <textarea
            id="spotfix-text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
          />
          {/* Disabled while a re-render is in flight, so a second confirm
              cannot race the first: both would write the same output path and
              the later response would not necessarily be the later write. */}
          <button onClick={confirm} disabled={busy || draft === current.translation}>
            {busy ? "Re-rendering…" : "Re-render this page"}
          </button>
        </div>
      )}
    </section>
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
