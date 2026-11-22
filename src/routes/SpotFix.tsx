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
import { ErrorAlert } from "../components/ErrorAlert";
import { Icon } from "../components/Icon";
import { NeedsAttention } from "../components/NeedsAttention";
import {
  api,
  describeError,
  loadSettings,
  type DismissedRegion,
  type ItemPages,
  type JobItem,
  type PageRecord,
  type Region,
  type RepackStatus,
  type StillSkipped,
} from "../lib/api";
import { pageUrl } from "../lib/pageUrl";

/** OCR's own set-aside: nothing a translation could change. */
const PUNCTUATION = "punctuation only";

/** The zoom steps, as a share of the frame's width; "fit" shows the whole page. */
const ZOOMS = [0.5, 0.75, 1, 1.5, 2];
type Zoom = "fit" | number;

/** A CSS colour token, read at draw time so the canvas follows the theme. */
function token(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

/** Controls whose own arrow keys move something: a caret, a choice, a value.
 *  A button does not -- after a click on a page chip, -> must still turn. */
const OWNS_ARROWS =
  "input,textarea,select,[role=listbox],[role=option],[role=combobox],[role=slider],[role=radiogroup],[role=radio],[role=tablist],[contenteditable=true]";
/** ...and Space as well clicks a button, a link or a disclosure. */
const OWNS_SPACE = `${OWNS_ARROWS},button,a[href],summary`;

/** Taller than this many widths is a strip: Fit fits its width, not its height. */
const STRIP_RATIO = 3;
/** Ctrl+wheel delta per zoom step: one notch of a mouse wheel, many trackpad events. */
const WHEEL_STEP = 100;

/** The decoded images of one page record, so a redraw does not fetch again. */
interface PageArt {
  page: PageRecord;
  out: HTMLImageElement;
  /** The original, once decoded; null while loading or when there is none. */
  orig: HTMLImageElement | null;
  /** The original was listed but did not load (evicted, or not allowed). */
  origFailed: boolean;
}

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
  item,
  items,
  onSwitchItem,
  page,
  onSelectPage,
  onPage,
  onRetried,
  manualPage,
  onManualPage,
  blocked,
}: {
  /** The open item: its pages, and the JOB's language and output folder --
   *  a re-render under another language is a cache miss by design (the
   *  mixed-language guard), so it must be the job's, never the form's. */
  item: ItemPages;
  /** The queue's items, for the switcher. */
  items: JobItem[];
  onSwitchItem: (itemId: string) => Promise<void>;
  page: PageRecord;
  onSelectPage: (p: PageRecord) => void;
  /** Called with the server's fresh record after every successful re-render. */
  onPage: (p: PageRecord) => void;
  /** Pages a retry brought back, fixed or still not translated. */
  onRetried: (pages: (PageRecord | StillSkipped)[]) => void;
  /** The page open in hand-translation mode, if any. */
  manualPage: number | null;
  onManualPage: (ordinal: number | null) => void;
  /** Why the sidecar would refuse a retry or a hand render right now. */
  blocked: string;
}) {
  const job = item.job_id;
  const pages = item.pages;
  const destDir = item.dest_dir;
  const lang = item.lang;
  const manual = page.skipped != null && manualPage === page.page;
  const canvas = useRef<HTMLCanvasElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const strip = useRef<HTMLElement>(null);
  // Fit by default: the whole page in view, the way it is read (plan 4.2).
  const [zoom, setZoom] = useState<Zoom>("fit");
  // The original page instead of the translated one: pinned by the button,
  // or held with Space for a quick before/after.
  const [pinOriginal, setPinOriginal] = useState(false);
  const [holdOriginal, setHoldOriginal] = useState(false);
  const [art, setArt] = useState<PageArt | null>(null);
  // Bumped when the theme changes: the canvas colours are CSS tokens read at
  // draw time, and nothing else in the draw effect changes with the theme.
  const [themeTick, setThemeTick] = useState(0);
  const artNow = art?.page === page ? art : null;
  const hasOriginal = !!page.original && !artNow?.origFailed;
  const showOriginal = (pinOriginal || holdOriginal) && hasOriginal;
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  // Text typed and not yet rendered: turning the page with a key would drop it.
  const selectedText =
    selected == null ? "" : (page.regions.find((r) => r.id === selected)?.translation ?? "");
  const unsaved = selected != null && draft !== selectedText;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [landed, setLanded] = useState(false);
  // The archive rebuild the last re-render scheduled. The loose page is
  // current the moment the response lands; the volume beside it is not, and
  // this is the one thing that says when it is.
  const [repack, setRepack] = useState<RepackStatus | null>(null);

  // Sorted for display only. The region objects themselves are the server's.
  const ordered = useMemo(
    () =>
      [...page.regions].sort(
        (a, b) => severity(a) - severity(b) || a.id - b.id,
      ),
    [page.regions],
  );
  // The model's nulls: left as drawn, and the user's to translate if the
  // model was wrong. Punctuation OCR set aside is not listed -- nothing there
  // a translation could change.
  const skipped = useMemo(
    () => (page.dismissed ?? []).filter((d) => d.editable),
    [page.dismissed],
  );
  // What gets a dashed outline: the model's nulls on a translated page, and
  // on a page that was not translated, every region OCR read as text.
  const outlined = useMemo(
    () =>
      page.skipped
        ? (page.dismissed ?? []).filter((d) => d.reason !== PUNCTUATION)
        : skipped,
    [page.skipped, page.dismissed, skipped],
  );

  // The delivered page, redrawn whenever the server hands back a new one. The
  // cache-buster is the point: the re-render writes to the SAME path, so
  // without it the browser shows the pre-edit image and the user concludes
  // nothing happened.
  //
  // A new page starts with nothing selected: page N's draft in page N+1's
  // bubble of the same number is one click from being rendered there. Keyed
  // on the ordinal, so a re-render's fresh record of this page keeps it.
  useEffect(() => {
    setSelected(null);
    setDraft("");
    setLanded(false);
    setError("");
  }, [page.page]);

  useEffect(() => {
    const watch = new MutationObserver(() => setThemeTick((n) => n + 1));
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => watch.disconnect();
  }, []);

  // Loaded once per record: a new selection or the original toggle redraws
  // from the decoded images instead of fetching and decoding the page again.
  useEffect(() => {
    let live = true;
    const out = new Image();
    out.onload = () => {
      if (!live) return;
      setArt({ page, out, orig: null, origFailed: false });
      if (!page.original) return;
      // After the page itself, so the toggle never delays the page.
      const orig = new Image();
      const settle = (patch: Partial<PageArt>) => {
        if (live) setArt((a) => (a && a.page === page ? { ...a, ...patch } : a));
      };
      orig.onload = () => settle({ orig });
      orig.onerror = () => settle({ origFailed: true });
      orig.src = pageUrl(page.original);
    };
    // No cache-buster on a data: URL: a query string would corrupt it, and an
    // inline image cannot be stale anyway.
    out.src = pageUrl(page.output, Date.now());
    return () => {
      live = false;
    };
  }, [page]);

  useEffect(() => {
    const el = canvas.current;
    // Until the new record's page decodes, the last one stays on screen.
    if (!el || !artNow) return;
    const colour = {
      selected: token("--accent", "#22c55e"),
      failed: token("--danger", "#ef4444"),
      tight: token("--warn", "#f59e0b"),
      skipped: token("--fg-faint", "#64748b"),
    };
    // Resized only when the page's size changes: assigning width reallocates
    // the backing store, about 96 MB for a 4000 x 6000 page, on every toggle.
    if (el.width !== artNow.out.naturalWidth) el.width = artNow.out.naturalWidth;
    if (el.height !== artNow.out.naturalHeight) el.height = artNow.out.naturalHeight;
    const ctx = el.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, el.width, el.height);
    ctx.drawImage(artNow.out, 0, 0);
    if (showOriginal && artNow.orig) {
      // The original is a smaller JPEG; drawn at the page's own size, so
      // the canvas keeps its geometry and the toggle does not jump.
      ctx.drawImage(artNow.orig, 0, 0, el.width, el.height);
      return;
    }
    for (const r of page.regions) {
      if (!r.fit_failed && !r.fit_compromised && r.id !== selected) continue;
      ctx.beginPath();
      laidInto(r).forEach(([x, y], i) =>
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y),
      );
      ctx.closePath();
      ctx.lineWidth = 3;
      ctx.strokeStyle =
        r.id === selected ? colour.selected : r.fit_failed ? colour.failed : colour.tight;
      ctx.stroke();
    }
    // Skipped regions dashed, so the user can find what the model left
    // untranslated without it reading as a problem the typesetter had.
    ctx.setLineDash([10, 6]);
    for (const d of outlined) {
      ctx.beginPath();
      d.polygon.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
      ctx.closePath();
      ctx.lineWidth = 3;
      ctx.strokeStyle = d.id === selected ? colour.selected : colour.skipped;
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }, [artNow, page.regions, selected, outlined, showOriginal, themeTick]);

  // Left/Right turn the page; Space held shows the original. Not when the
  // focused control owns the key, and never a page turn that would drop text
  // typed and not yet rendered: the hand-translation fields, or a draft.
  useEffect(() => {
    function owned(e: KeyboardEvent, by: string) {
      const el = e.target instanceof Element ? e.target : null;
      return e.defaultPrevented || !!el?.closest(by) || !!(el as HTMLElement | null)?.isContentEditable;
    }
    function down(e: KeyboardEvent) {
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      if (owned(e, e.key === " " ? OWNS_SPACE : OWNS_ARROWS)) return;
      const at = pages.findIndex((p) => p.page === page.page);
      const turn = e.key === "ArrowLeft" ? -1 : e.key === "ArrowRight" ? 1 : 0;
      if (turn !== 0) {
        if (manual || unsaved) return;
        const next = pages[at + turn];
        if (at < 0 || !next) return;
        e.preventDefault();
        onSelectPage(next);
      } else if (e.key === " " && hasOriginal) {
        e.preventDefault();
        setHoldOriginal(true);
      }
    }
    function up(e: KeyboardEvent) {
      if (e.key === " ") setHoldOriginal(false);
    }
    // A Space held while the window loses focus never sends its keyup.
    function release() {
      setHoldOriginal(false);
    }
    function hidden() {
      if (document.hidden) release();
    }
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", release);
    document.addEventListener("visibilitychange", hidden);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", release);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, [pages, page, onSelectPage, manual, unsaved, hasOriginal]);

  // Ctrl+wheel zooms. A native listener: React's wheel handler is passive,
  // and the page would scroll as well as zoom.
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    // Accumulated: a trackpad pinch sends dozens of small events, and a step
    // per event ran straight to the end of the range.
    let acc = 0;
    function wheel(e: WheelEvent) {
      if (!e.ctrlKey) return;
      e.preventDefault();
      acc += e.deltaY;
      if (Math.abs(acc) < WHEEL_STEP) return;
      const dir = acc < 0 ? 1 : -1;
      acc = 0;
      setZoom((z) => {
        const now = z === "fit" ? 1 : z;
        const i = ZOOMS.findIndex((v) => v >= now);
        const at = i < 0 ? ZOOMS.length - 1 : i;
        return ZOOMS[Math.max(0, Math.min(ZOOMS.length - 1, at + dir))];
      });
    }
    el.addEventListener("wheel", wheel, { passive: false });
    return () => el.removeEventListener("wheel", wheel);
  }, []);

  // The current page's chip stays in view as the page changes.
  // The strip alone scrolls: scrollIntoView would move the window as well.
  useEffect(() => {
    const bar = strip.current;
    const chip = bar?.querySelector<HTMLElement>('[aria-current="true"]');
    if (!bar || !chip) return;
    // From the rendered boxes, so it holds whatever the strip's positioning.
    const left = chip.getBoundingClientRect().left - bar.getBoundingClientRect().left + bar.scrollLeft;
    if (left < bar.scrollLeft) bar.scrollLeft = left;
    else if (left + chip.offsetWidth > bar.scrollLeft + bar.clientWidth)
      bar.scrollLeft = left + chip.offsetWidth - bar.clientWidth;
  }, [page.page]);

  function stepZoom(dir: 1 | -1) {
    setZoom((z) => {
      const now = z === "fit" ? 1 : z;
      const i = ZOOMS.indexOf(now);
      return ZOOMS[Math.max(0, Math.min(ZOOMS.length - 1, (i < 0 ? 2 : i) + dir))];
    });
  }
  const isStrip =
    !!artNow && artNow.out.naturalHeight > artNow.out.naturalWidth * STRIP_RATIO;
  const canvasStyle: CSSProperties =
    zoom !== "fit"
      ? { width: `${Math.round(zoom * 100)}%`, maxWidth: "none", maxHeight: "none" }
      : isStrip
        ? // Fitting a 720 x 20000 strip's height leaves an 18 px sliver.
          { width: "100%", maxWidth: "100%", maxHeight: "none" }
        : { maxHeight: "max(320px, calc(100vh - 420px))", width: "auto", maxWidth: "100%" };

  function pick(e: React.MouseEvent<HTMLCanvasElement>) {
    const el = canvas.current;
    if (!el) return;
    if (showOriginal) return; // nothing to pick on the page as drawn
    // The new record's page has not decoded: the canvas still shows the last
    // one, and a hit here would select a bubble the user cannot see.
    if (!artNow) return;
    const box = el.getBoundingClientRect();
    // Divide the display scale out. el.width is the PAGE width; box.width is
    // however many screen pixels it is currently shown in.
    const x = ((e.clientX - box.left) * el.width) / box.width;
    const y = ((e.clientY - box.top) * el.height) / box.height;
    const hit = page.regions.find((r) => inPolygon(x, y, laidInto(r)));
    if (hit) return select(hit);
    const miss = outlined.find((d) => inPolygon(x, y, d.polygon));
    if (!miss) return;
    if (manual) {
      // In hand mode a click on the page goes to that bubble's field.
      setSelected(miss.id);
      document.getElementById(`manual-${miss.id}`)?.focus();
      return;
    }
    if (!page.skipped) select(miss);
  }

  /** A skipped region starts from an empty draft: it has no translation. */
  function select(r: Region | DismissedRegion) {
    setSelected(r.id);
    setDraft("translation" in r ? r.translation : "");
    setError("");
    setLanded(false);
  }

  useEffect(() => {
    if (!landed) return;
    const t = setTimeout(() => setLanded(false), 2500);
    return () => clearTimeout(t);
  }, [landed]);

  // Poll while the worker is pending or running. It is a dictionary read on
  // the sidecar, so 500ms costs nothing; the interval ends itself the moment
  // the status settles, and a re-render mid-poll restarts it on the fresh
  // status through the dependency.
  useEffect(() => {
    if (!repack || (repack.status !== "pending" && repack.status !== "running")) return;
    let cancelled = false;
    const t = setInterval(async () => {
      try {
        const next = await api.repackStatus(job, page.item_id);
        if (!cancelled) setRepack(next);
      } catch {
        // The sidecar answers this from memory; a failure here is the
        // sidecar going away, which the app shell already reports.
      }
    }, 500);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [repack, job, page.item_id]);

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
      if (fresh.archive_stale) setRepack(fresh.repack ?? { ...UNREPACKABLE });
    } catch (e) {
      // describeError, never a synonym: the provider's own status and body
      // reach the user verbatim (AC-8).
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  const openable = items.filter((i) => i.status === "ok");
  const current = ordered.find((r) => r.id === selected) ?? null;
  const currentSkipped = current ? null : (skipped.find((d) => d.id === selected) ?? null);
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
        {openable.length > 1 && (
          <div className="field item-switch">
            <label className="label" htmlFor="item-switch">
              Chapter
            </label>
            <select
              id="item-switch"
              value={item.item_id}
              onChange={(e) => {
                setError("");
                onSwitchItem(e.target.value).catch((err) => setError(describeError(err)));
              }}
            >
              {openable.map((i) => (
                <option key={i.item_id} value={i.item_id}>
                  {i.item_id}
                  {i.pages_skipped.length ? ` (${i.pages_skipped.length} not translated)` : ""}
                </option>
              ))}
            </select>
          </div>
        )}
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
          {failed === 0 && tight === 0 && !page.skipped && (
            <span className="pill ok">
              <Icon name="check" size={12} />
              Every bubble fits
            </span>
          )}
          {skipped.length > 0 && (
            <span className="pill">
              <Icon name="skip-forward" size={12} />
              {skipped.length} skipped
            </span>
          )}
          {repack && (repack.status === "pending" || repack.status === "running") && (
            <span className="pill running" role="status">
              <Icon name="loader" size={12} />
              Updating archive…
            </span>
          )}
          {repack?.status === "done" && (
            <span className="pill ok" role="status">
              <Icon name="check" size={12} />
              Archive up to date
            </span>
          )}
        </div>
      </div>

      <nav className="page-strip" aria-label="Pages" ref={strip}>
        {pages.map((p) => {
          const f = p.fit_summary?.fit_failed?.length ?? 0;
          const c = p.fit_summary?.fit_compromised?.length ?? 0;
          return (
            <button
              key={p.page}
              type="button"
              className="chip thumb-chip"
              onClick={() => onSelectPage(p)}
              aria-current={p.page === page.page ? "true" : undefined}
              aria-label={`Page ${p.page}${p.skipped ? ", not translated" : f ? `, ${f} did not fit` : c ? `, ${c} tight` : ""}`}
            >
              <img
                key={p.thumb || p.output}
                src={pageUrl(p.thumb || p.output)}
                alt=""
                loading="lazy"
                decoding="async"
                onError={(e) => {
                  // The thumbnail evicted, or its folder not allowed: the
                  // delivered page is always there. Once, so a missing page
                  // does not loop.
                  const img = e.currentTarget;
                  if (img.dataset.fallback || !p.thumb) return void (img.style.visibility = "hidden");
                  img.dataset.fallback = "1";
                  img.src = pageUrl(p.output);
                }}
              />
              <span className="chip-label">
                {p.page}
                {p.skipped ? (
                  <Icon name="skip-forward" size={11} />
                ) : f > 0 ? (
                  <span className="mark" />
                ) : c > 0 ? (
                  <span className="mark warn" />
                ) : null}
              </span>
            </button>
          );
        })}
      </nav>

      {page.skipped && (
        <Alert tone="warn" title="This page was not translated">
          {page.skipped.message} The original page is in its slot, so the chapter stays in
          order.
          {page.skipped.remembered &&
            " This model refused it on an earlier run, so it was not asked again."}
          {page.skipped.detail && (
            <details style={{ marginTop: 6 }}>
              <summary>Details from the provider</summary>
              <code className="alert-path">{page.skipped.detail}</code>
            </details>
          )}
        </Alert>
      )}
      {page.choice && (
        <Alert tone="info">
          {page.choice.mode === "manual"
            ? "You translated this page by hand."
            : page.choice.mode === "text_only"
              ? `Translated without the page image (${page.choice.model.replace(/#text$/, "")}). Check that no artwork was erased as text.`
              : page.choice.mode === "vision"
                ? `Retried with ${page.choice.model} after it was skipped.`
                : `Translated with ${page.choice.model}, which you picked for this page.`}
        </Alert>
      )}
      {page.cache_warning && <Alert tone="warn">{page.cache_warning}</Alert>}
      {page.edit_on_other_model && (
        <Alert tone="info">
          This page has an edit saved against a different model. It is kept, and it
          is not being used here.
        </Alert>
      )}
      <ErrorAlert error={error} />
      {repack?.status === "failed" && (
        <Alert tone="warn">
          The page was re-rendered, but the archive beside it was not rebuilt:{" "}
          {repack.error || "the sidecar has no record of where this item came from -- run it again to rebuild the archive."}
        </Alert>
      )}

      <div className="editor-grid">
        <div className="canvas-frame">
          <div className="canvas-tools" role="group" aria-label="Page view">
            <button
              type="button"
              className="btn sm"
              onClick={() => setZoom("fit")}
              aria-pressed={zoom === "fit"}
              title="Fit the whole page"
            >
              Fit
            </button>
            <button type="button" className="btn icon sm" onClick={() => stepZoom(-1)} aria-label="Zoom out">
              −
            </button>
            <span className="zoom-level mono" aria-live="polite">
              {zoom === "fit" ? "fit" : `${Math.round(zoom * 100)}%`}
            </span>
            <button type="button" className="btn icon sm" onClick={() => stepZoom(1)} aria-label="Zoom in">
              +
            </button>
            <span className="spacer" />
            <button
              type="button"
              className="btn sm"
              onClick={() => {
                // Off clears a stuck hold as well as the pin.
                if (showOriginal) {
                  setPinOriginal(false);
                  setHoldOriginal(false);
                } else setPinOriginal(true);
              }}
              aria-pressed={showOriginal}
              aria-keyshortcuts="Space"
              disabled={!hasOriginal}
              aria-describedby={hasOriginal ? undefined : "no-original"}
              title={
                hasOriginal
                  ? "Show the page as it came in (or hold Space)"
                  : "No original saved for this page: run the chapter again to get one"
              }
            >
              <Icon name={showOriginal ? "eye-off" : "eye"} size={14} />
              Original
            </button>
          </div>
          {!hasOriginal && (
            <span id="no-original" className="sr-only">
              No original saved for this page: run the chapter again to get one.
            </span>
          )}
          <div className="canvas-scroll" ref={scroller}>
            <canvas
              ref={canvas}
              onClick={pick}
              className="page"
              style={canvasStyle}
              aria-label={
                showOriginal
                  ? `Page ${page.page}, ${page.member}, as it came in.`
                  : `Page ${page.page}, ${page.member}. Click a bubble to select it.`
              }
            />
          </div>
          <div className="legend" aria-hidden>
            <span>
              <i style={{ background: "var(--accent)" }} /> selected
            </span>
            <span>
              <i style={{ background: "var(--danger)" }} /> did not fit
            </span>
            <span>
              <i style={{ background: "var(--warn)" }} /> tight
            </span>
            {outlined.length > 0 && (
              <span>
                <i
                  style={{
                    background: "transparent",
                    outline: "2px dashed var(--fg-faint)",
                    outlineOffset: -2,
                  }}
                />{" "}
                {page.skipped ? "not translated" : "skipped"}
              </span>
            )}
            <span className="faint">← → pages · Space original</span>
            <span className="spacer" />
            <span className="mono">{page.member}</span>
          </div>
        </div>

        <div className="stack">
          {!page.skipped && (
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
                <li className="empty">
                  {page.skipped
                    ? `Not translated: ${page.dismissed?.length ?? 0} bubbles are left as drawn.`
                    : skipped.length
                      ? "Nothing on this page was translated."
                      : "No text was detected on this page."}
                </li>
              )}
            </ol>
            {skipped.length > 0 && (
              <>
                <h3 className="regions-sub">Skipped by the model · {skipped.length}</h3>
                <p className="regions-note">
                  Marked as not text, so left as drawn. Pick one to translate it yourself.
                </p>
                <ol className="regions">
                  {skipped.map((d) => (
                    <li key={d.id}>
                      <button
                        type="button"
                        className="region"
                        onClick={() => select(d)}
                        disabled={busy}
                        aria-pressed={d.id === selected}
                      >
                        <span className="top">
                          <span className="id">#{d.id}</span>
                          <span className="flag skipped">
                            <Icon name="skip-forward" size={12} />
                            skipped
                          </span>
                        </span>
                        {d.text && <span className="text" lang={page.source ?? "ja"}>{d.text}</span>}
                      </button>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </section>
          )}

          {page.skipped ? (
            manual ? (
              <ManualPanel
                key={`manual-${page.page}`}
                item={item}
                page={page}
                focus={selected}
                onFocus={setSelected}
                onDone={(fresh) => {
                  setSelected(null);
                  onManualPage(null);
                  onPage(fresh);
                }}
                onCancel={() => onManualPage(null)}
                blocked={blocked}
              />
            ) : (
              <NeedsAttention
                key={`attention-${page.page}`}
                compact
                jobId={job}
                itemId={item.item_id}
                pages={[page]}
                lang={lang}
                destDir={destDir}
                onRetried={onRetried}
                onTranslateMyself={(n) => onManualPage(n)}
                blocked={blocked}
              />
            )
          ) : current ? (
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
          ) : currentSkipped ? (
            <section className="card stack" key={`skipped-${currentSkipped.id}`}>
              <div className="card-head" style={{ marginBottom: 0 }}>
                <span className="icon-tile">
                  <Icon name="skip-forward" />
                </span>
                <div>
                  <h2>Skipped #{currentSkipped.id}</h2>
                  <p className="sub">Left as drawn. Ctrl+Enter erases it and draws yours.</p>
                </div>
              </div>
              {currentSkipped.text && (
                <div className="source-text" lang={page.source ?? "ja"}>{currentSkipped.text}</div>
              )}
              <div className="field">
                <label className="label" htmlFor="spotfix-text">
                  Translation
                </label>
                <textarea
                  id="spotfix-text"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && draft.trim()) {
                      e.preventDefault();
                      confirm();
                    }
                  }}
                  rows={4}
                  disabled={busy}
                  aria-describedby="skipped-hint"
                />
                <span id="skipped-hint" className="hint">
                  The model marked this as not text. If it is, type the translation and the
                  original lettering is erased under it.
                </span>
              </div>
              <div className="row end">
                <button
                  className="btn primary"
                  onClick={confirm}
                  disabled={busy || !draft.trim()}
                >
                  {busy ? <Icon name="loader" className="spin" /> : <Icon name="pencil" />}
                  {busy ? "Re-rendering…" : "Translate this bubble"}
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

/** What a re-render reports when the sidecar cannot rebuild the archive at
 *  all -- a placement from before it recorded the item's input. Rendered
 *  as the failed alert, with its own reason. */
const UNREPACKABLE: RepackStatus = {
  status: "failed",
  archive: "",
  error: "",
  edits: 0,
  repacks: 0,
};

/**
 * Hand-translation of a page that was not translated (plan Phase 3.4): every
 * region OCR read, each with its own field, then ONE render. A field left
 * empty keeps that bubble as drawn -- the sidecar stores it as a decided
 * "no text here", so no later run sends the page back to the model that
 * refused it. Nothing here asks a model.
 */
function ManualPanel({
  item,
  page,
  focus,
  onFocus,
  onDone,
  onCancel,
  blocked,
}: {
  item: ItemPages;
  page: PageRecord;
  blocked: string;
  focus: number | null;
  onFocus: (id: number) => void;
  onDone: (fresh: PageRecord) => void;
  onCancel: () => void;
}) {
  const regions = (page.dismissed ?? []).filter((d) => d.reason !== PUNCTUATION);
  const [texts, setTexts] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const filled = regions.filter((r) => (texts[r.id] ?? "").trim()).length;

  async function render() {
    setBusy(true);
    setError("");
    try {
      const typed: Record<string, string> = {};
      for (const r of regions) {
        const t = (texts[r.id] ?? "").trim();
        if (t) typed[String(r.id)] = t;
      }
      onDone(
        await api.pages.manual({
          job_id: item.job_id,
          item_id: item.item_id,
          ordinal: page.page,
          dest_dir: item.dest_dir,
          lang: item.lang,
          texts: typed,
        }),
      );
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card stack manual-panel">
      <div className="card-head" style={{ marginBottom: 0 }}>
        <span className="icon-tile">
          <Icon name="pencil" />
        </span>
        <div>
          <h2>Translate page {page.page} yourself</h2>
          <p className="sub">Type each bubble. Leave one empty to keep it as drawn.</p>
        </div>
      </div>
      <ol className="manual-list">
        {regions.map((r) => (
          <li key={r.id} className={focus === r.id ? "focused" : undefined}>
            <label className="label" htmlFor={`manual-${r.id}`}>
              #{r.id}
              {r.text && (
                <span className="source-text inline" lang={page.source ?? "ja"}>
                  {r.text}
                </span>
              )}
            </label>
            <textarea
              id={`manual-${r.id}`}
              rows={2}
              value={texts[r.id] ?? ""}
              onFocus={() => onFocus(r.id)}
              onChange={(e) => setTexts((prev) => ({ ...prev, [r.id]: e.target.value }))}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && !blocked) {
                  e.preventDefault();
                  void render();
                }
              }}
              disabled={busy}
            />
          </li>
        ))}
        {regions.length === 0 && <li className="empty">No text was detected on this page.</li>}
      </ol>
      <ErrorAlert error={error} />
      {blocked && <p className="hint">{blocked}</p>}
      <div className="row end">
        <button type="button" className="btn ghost" onClick={onCancel} disabled={busy}>
          Back
        </button>
        {/* With nothing typed, the page is accepted as drawn: every bubble
            stays, and it stops counting as not translated. */}
        <button type="button" className="btn primary" onClick={render} disabled={busy || !!blocked}>
          {busy ? <Icon name="loader" className="spin" /> : <Icon name="refresh" />}
          {busy
            ? "Rendering…"
            : filled
              ? `Render page (${filled} of ${regions.length})`
              : "Keep the page as drawn"}
        </button>
      </div>
      <p className="hint">Ctrl+Enter renders.</p>
    </section>
  );
}
