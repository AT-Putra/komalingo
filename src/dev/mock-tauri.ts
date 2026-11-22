/**
 * A stand-in for the Tauri runtime, so `npm run dev` in a plain browser shows
 * every view with plausible data. Dev only: main.tsx imports it only when
 * import.meta.env.DEV is true and no real runtime is present, and Vite drops
 * the import from production bundles.
 *
 * It fakes the four things the app touches: the `api` proxy command, the
 * sidecar start/stop commands, the event plugin (progress and log lines), and
 * the dialog plugin. Timings are compressed -- a page takes about two seconds
 * -- so the progress widgets can be watched moving without a model.
 *
 * Nothing here is a fixture for the checks. tests/ never imports it.
 */

import type { ItemPages, JobStatus, PageRecord, Region, RetryStatus } from "../lib/api";

type Callback = (e: { event: string; id: number; payload: unknown }) => void;

const callbacks = new Map<number, Callback>();
const listeners = new Map<string, Set<number>>();
let nextId = 1;

function emit(event: string, payload: unknown) {
  for (const id of listeners.get(event) ?? []) {
    callbacks.get(id)?.({ event, id, payload });
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const STAGES: [string, number][] = [
  ["detect", 10],
  ["ocr", 25],
  ["translate", 50],
  ["inpaint", 65],
  ["render", 80],
  ["encode", 90],
  ["write", 100],
];

/** A white page with a few bubbles, drawn on the spot. */
function pageImage(n: number, regions: Region[]): string {
  const c = document.createElement("canvas");
  c.width = 900;
  c.height = 1300;
  const ctx = c.getContext("2d")!;
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, c.width, c.height);
  ctx.strokeStyle = "#111";
  ctx.lineWidth = 6;
  ctx.strokeRect(40, 40, 820, 1220);
  ctx.beginPath();
  ctx.moveTo(40, 640);
  ctx.lineTo(860, 640);
  ctx.stroke();
  ctx.fillStyle = "#e7e7e7";
  ctx.fillRect(60, 60, 780, 560);
  ctx.fillRect(60, 660, 780, 580);
  for (const r of regions) {
    const xs = r.polygon.map((p) => p[0]);
    const ys = r.polygon.map((p) => p[1]);
    const x = Math.min(...xs), y = Math.min(...ys);
    const w = Math.max(...xs) - x, h = Math.max(...ys) - y;
    ctx.beginPath();
    ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
    ctx.fillStyle = "#fff";
    ctx.fill();
    ctx.strokeStyle = "#111";
    ctx.lineWidth = 4;
    ctx.stroke();
    ctx.fillStyle = "#111";
    ctx.font = "bold 28px sans-serif";
    ctx.textAlign = "center";
    const words = r.typeset.split(" ");
    words.forEach((word, i) =>
      ctx.fillText(word, x + w / 2, y + h / 2 - ((words.length - 1) * 16) + i * 32),
    );
  }
  ctx.fillStyle = "#111";
  ctx.font = "20px sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(`${n}`, 840, 1290);
  return c.toDataURL("image/png");
}

function rect(x: number, y: number, w: number, h: number): [number, number][] {
  return [
    [x, y],
    [x + w, y],
    [x + w, y + h],
    [x, y + h],
  ];
}

function fakePage(item_id: string, n: number): PageRecord {
  const regions: Region[] = [
    {
      id: 1,
      polygon: rect(120, 120, 300, 160),
      text: "ここは……どこだ？",
      translation: "Where... am I?",
      typeset: "Where... am I?",
      fit_compromised: false,
      fit_failed: false,
    },
    {
      id: 2,
      polygon: rect(520, 300, 280, 150),
      text: "逃げろ！！",
      translation: n === 2 ? "Run for your lives, everyone, right now!" : "Run!!",
      typeset: n === 2 ? "Run for your lives, everyone, right now!" : "Run!!",
      fit_compromised: n === 3,
      fit_failed: n === 2,
      fit_reason: n === 2 ? "no width for the longest word" : undefined,
    },
    {
      id: 3,
      polygon: rect(160, 760, 340, 180),
      text: "大丈夫だ。私がついている。",
      translation: "It's alright. I'm with you.",
      typeset: "It's alright. I'm with you.",
      fit_compromised: false,
      fit_failed: false,
    },
  ];
  return {
    page: n,
    page_hash: `hash-${item_id}-${n}`,
    item_id,
    member: `${String(n).padStart(3, "0")}.png`,
    output: pageImage(n, regions),
    cached: false,
    detections: regions.length,
    regions,
    // One line the vision model called art, for the editor's skipped list.
    dismissed: [
      {
        id: 4,
        polygon: rect(560, 820, 240, 110),
        text: "ふふっ",
        reason: "not on the page (vision model)",
        editable: true,
      },
    ],
    fit_summary: {
      fit_compromised: regions.filter((r) => r.fit_compromised).map((r) => r.id),
      fit_failed: regions.filter((r) => r.fit_failed).map((r) => r.id),
      retranslated: [],
    },
  };
}

async function runPages(item: string, pages: number, perStage: number) {
  for (let p = 1; p <= pages; p++) {
    for (const [stage, pct] of STAGES) {
      await sleep(perStage);
      // `total` as the sidecar sends it, so the chapter bar can be watched
      // moving here too (sidecar/pipeline.emit).
      emit("sidecar-progress", {
        stage,
        item: `${1 + (p % 3)} regions`,
        page: p,
        pct,
        total: pages,
      });
    }
    emit("sidecar-log", `INFO ${item} page ${p} written`);
  }
}

/** A page the model refused: the original in its slot, nothing translated. */
function skippedPage(item_id: string, n: number): PageRecord {
  const base = fakePage(item_id, n);
  return {
    ...base,
    output: pageImage(n, []),
    detections: 0,
    regions: [],
    dismissed: base.regions.map((r) => ({
      id: r.id, polygon: r.polygon, text: r.text, reason: "the page was skipped", editable: false,
    })),
    fit_summary: { fit_compromised: [], fit_failed: [], retranslated: [] },
    skipped: {
      kind: "refused",
      message: "The model refused to translate this page.",
      detail: '{"code":403,"message":"Your chosen model requires moderation and your input was flagged","metadata":{"reasons":["violence"]}}',
      status: 403,
      model: "gpt-4o",
      with_image: true,
    },
  };
}

const jobs = new Map<string, JobStatus>();
// Every finished item's page records, by `${job}/${item}`.
const itemPages = new Map<string, PageRecord[]>();
const retries = new Map<string, RetryStatus>();
// Items whose page `n` the mock model refuses, and the one item that makes
// the provider refuse the ACCOUNT -- so the Queue's skipped counts and its
// pause banner can both be seen in a browser.
const REFUSED_PAGES: Record<string, number[]> = { v02: [2], ch05: [1, 2] };
const PAUSES_ON = "v04";

async function runJob(job: JobStatus) {
  for (const item of job.items) {
    // A resumed job runs only what the pause left, as the sidecar's does.
    if (item.status !== "pending") continue;
    if (job.cancelled) {
      if (item.status === "pending") {
        item.status = "cancelled";
        job.cancelled_items++;
        job.pending--;
      }
      continue;
    }
    if (item.kind === "unsupported") {
      item.status = "skipped";
      item.reason = "not an image, PDF or archive";
      job.skipped++;
      job.pending--;
      emit("sidecar-progress", { stage: "item_start", item: item.item_id, page: 0, pct: 0 });
      emit("sidecar-progress", { stage: "item_done", item: item.item_id, page: 0, pct: 100 });
      continue;
    }
    if (job.paused) continue; // a paused job claims nothing more
    job.pending--;
    job.running++;
    item.pages_total = item.pages;
    emit("sidecar-progress", { stage: "item_start", item: item.item_id, page: 0, pct: 0 });
    if (item.item_id === PAUSES_ON && !resumed.has(job.job_id)) {
      await runPages(item.item_id, 1, 120);
      job.running--;
      item.status = "paused";
      item.reason = "paused before its first page";
      job.paused = true;
      job.paused_items++;
      job.pause_reason =
        'The provider refused the account (HTTP 401): {"error":{"message":"Incorrect API key provided"}}';
      emit("sidecar-progress", { stage: "item_done", item: item.item_id, page: 0, pct: 100 });
      continue;
    }
    for (let p = 1; p <= item.pages; p++) {
      await runPages(item.item_id, 1, 120);
      item.pages_done = p;
      if (REFUSED_PAGES[item.item_id]?.includes(p)) {
        item.pages_skipped.push({
          ordinal: p, member: `${String(p).padStart(3, "0")}.png`, kind: "refused",
          message: "The model refused to translate this page.",
        });
        job.pages_skipped++;
      }
    }
    job.running--;
    itemPages.set(
      `${job.job_id}/${item.item_id}`,
      Array.from({ length: item.pages }, (_, k) =>
        REFUSED_PAGES[item.item_id]?.includes(k + 1)
          ? skippedPage(item.item_id, k + 1)
          : fakePage(item.item_id, k + 1),
      ),
    );
    if (item.item_id.includes("corrupt")) {
      item.status = "failed";
      item.reason = "zip: central directory not found";
      job.failed++;
    } else {
      item.status = "ok";
      job.ok++;
    }
    emit("sidecar-progress", { stage: "item_done", item: item.item_id, page: item.pages, pct: 100 });
  }
  job.done = true;
}

// Jobs resumed once: the mock's "fixed key" lets the paused item through.
const resumed = new Set<string>();

// The page cache the Settings card reads; a clear empties it for the session.
let mockCache = { bytes: 851_968_000, pages: 214, edited_pages: 3 };

async function api(path: string, method: string, body: Record<string, unknown> | null) {
  if (path === "/api/health") return { status: "ok", pid: 4242 };
  if (path.startsWith("/api/models")) {
    await sleep(500);
    // Enough rows to scroll and to filter: what an aggregator answers.
    return {
      models: [
        { id: "gpt-4o", owned_by: "openai" },
        { id: "gpt-4o-mini", owned_by: "openai" },
        { id: "gpt-4.1", owned_by: "openai" },
        { id: "claude-sonnet-4", owned_by: "anthropic" },
        { id: "claude-opus-4", owned_by: "anthropic" },
        { id: "gemini-2.5-pro", owned_by: "google" },
        { id: "gemini-2.5-flash", owned_by: "google" },
        { id: "qwen2.5-vl-7b-instruct", owned_by: "local" },
        { id: "qwen2.5-vl-72b-instruct", owned_by: "combo" },
        { id: "llama-3.2-11b-vision", owned_by: "local" },
        { id: "pixtral-12b", owned_by: "mistral" },
        { id: "deepseek-chat", owned_by: "deepseek" },
      ],
    };
  }
  if (path === "/api/translate") {
    await sleep(900);
    return {
      page: 1,
      // The real sidecar reports the long-path form it wrote through.
      output: `\\\\?\\${String(body?.dest_dir)}\\sample_translated.png`,
      detections: 4,
      ocr_calls: 1,
      inpaint_calls: 1,
      pixels_changed_in_polygon: {},
    };
  }
  const itemRoute = path.match(/^\/api\/job\/([^/]+)\/item\/([^/]+)$/);
  if (itemRoute) {
    const jobId = decodeURIComponent(itemRoute[1]);
    const itemId = decodeURIComponent(itemRoute[2]);
    const job = jobs.get(jobId);
    const it = job?.items.find((i) => i.item_id === itemId);
    if (!job || !it) throw { status: 404, body: '{"error":"no such item"}' };
    const result: ItemPages = {
      job_id: jobId,
      item_id: itemId,
      kind: it.kind,
      status: it.status,
      pages: structuredClone(itemPages.get(`${jobId}/${itemId}`) ?? []),
      cache_warning: null,
      lang: "en",
      dest_dir: "C:\\Manga\\translated",
    };
    return result;
  }
  if (path === "/api/pages/retry" && method === "POST") {
    // The mock's model refuses "as-is" again; without the image, or with
    // another model, the page comes back translated.
    const key = `${String(body?.job_id)}/${String(body?.item_id)}`;
    const ordinals = (body?.ordinals as number[]) ?? [];
    const mode = String(body?.mode) as RetryStatus["mode"];
    const st: RetryStatus = {
      status: "running", mode, model: String(body?.model ?? "gpt-4o"),
      total: ordinals.length, done: 0, pages: [], error: "", kind: "", repack: null,
    };
    retries.set(key, st);
    void (async () => {
      const job = jobs.get(String(body?.job_id));
      const it = job?.items.find((i) => i.item_id === String(body?.item_id));
      const pages = itemPages.get(key) ?? [];
      for (const n of ordinals) {
        await sleep(700);
        const at = pages.findIndex((p) => p.page === n);
        if (mode === "same") {
          st.pages.push({ page: n, page_hash: `hash-${n}`, item_id: String(body?.item_id), member: null,
                          skipped: { ...(pages[at]?.skipped ?? skippedPage("x", n).skipped!) } });
        } else {
          const fixed = fakePage(String(body?.item_id), n);
          fixed.choice = { model: mode === "text_only" ? "gpt-4o#text" : st.model, mode };
          if (at >= 0) pages[at] = fixed;
          st.pages.push(fixed);
          if (it && job) {
            it.pages_skipped = it.pages_skipped.filter((p) => p.ordinal !== n);
            job.pages_skipped--;
          }
        }
        st.done++;
      }
      st.status = "done";
    })();
    return structuredClone(st);
  }
  if (path.startsWith("/api/pages/retry")) {
    const q = new URLSearchParams(path.split("?")[1] ?? "");
    const st = retries.get(`${q.get("job_id")}/${q.get("item_id")}`);
    if (!st) throw { status: 404, body: '{"error":"no retry"}' };
    return structuredClone(st);
  }
  if (path === "/api/pages/manual" && method === "POST") {
    await sleep(600);
    const key = `${String(body?.job_id)}/${String(body?.item_id)}`;
    const n = Number(body?.ordinal);
    const texts = (body?.texts ?? {}) as Record<string, string>;
    const page = fakePage(String(body?.item_id), n);
    page.regions = page.regions
      .filter((r) => texts[String(r.id)])
      .map((r) => ({ ...r, translation: texts[String(r.id)], typeset: texts[String(r.id)],
                     edited: true, fit_failed: false, fit_compromised: false }));
    page.fit_summary = { fit_compromised: [], fit_failed: [], retranslated: [] };
    page.output = pageImage(n, page.regions);
    page.choice = { model: "#manual", mode: "manual" };
    const pages = itemPages.get(key) ?? [];
    const at = pages.findIndex((p) => p.page === n);
    if (at >= 0) pages[at] = page;
    const job = jobs.get(String(body?.job_id));
    const it = job?.items.find((i) => i.item_id === String(body?.item_id));
    if (it && job && it.pages_skipped.some((p) => p.ordinal === n)) {
      it.pages_skipped = it.pages_skipped.filter((p) => p.ordinal !== n);
      job.pages_skipped--;
    }
    return page;
  }
  if (path === "/api/rerender") {
    await sleep(700);
    const page = fakePage(String(body?.item_id), Number(body?.ordinal));
    // A skipped region translated by hand joins the page, as the sidecar does.
    const was = page.dismissed?.find((d) => d.id === Number(body?.region_id));
    if (was) {
      page.dismissed = page.dismissed?.filter((d) => d !== was);
      page.regions.push({
        id: was.id, polygon: was.polygon, text: was.text, translation: "", typeset: "",
        fit_compromised: false, fit_failed: false,
      });
    }
    const r = page.regions.find((x) => x.id === Number(body?.region_id));
    if (r) {
      r.translation = String(body?.text);
      r.typeset = r.translation;
      r.edited = true;
      r.fit_failed = r.translation.length > 30;
      r.fit_compromised = false;
      r.fit_reason = r.fit_failed ? "no width for the longest word" : undefined;
    }
    page.fit_summary.fit_failed = page.regions.filter((x) => x.fit_failed).map((x) => x.id);
    page.fit_summary.fit_compromised = page.regions
      .filter((x) => x.fit_compromised)
      .map((x) => x.id);
    page.output = pageImage(page.page, page.regions);
    return page;
  }
  if (path === "/api/cache") {
    await sleep(300);
    return {
      root: "C:\\Users\\reader\\AppData\\Local\\Komalingo\\cache",
      ...mockCache,
      cap_bytes: 4 * 1024 ** 3,
    };
  }
  if (path === "/api/cache/clear" && method === "POST") {
    await sleep(800);
    const r = { removed: mockCache.pages, held: 0, freed_bytes: mockCache.bytes, bytes: 0 };
    mockCache = { bytes: 0, pages: 0, edited_pages: 0 };
    return r;
  }
  if (path === "/api/job" && method === "POST") {
    const job_id = String(body?.job_id);
    const added = (body?.paths as string[] | undefined) ?? [];
    const firstName = added.length
      ? (added[0].split(/[\\/]/).filter(Boolean).pop() ?? "v01")
      : "v01";
    const job: JobStatus = {
      job_id,
      items: [
        { path: firstName, item_id: firstName, kind: "archive", status: "pending", reason: "", warning: "", output: "", pages: 4, pages_total: null, pages_done: 0, pages_skipped: [] },
        { path: "v02.cbz", item_id: "v02", kind: "archive", status: "pending", reason: "", warning: "", output: "", pages: 3, pages_total: null, pages_done: 0, pages_skipped: [] },
        { path: "notes.txt", item_id: "notes", kind: "unsupported", status: "pending", reason: "", warning: "", output: "", pages: 0, pages_total: null, pages_done: 0, pages_skipped: [] },
        { path: "ch05", item_id: "ch05", kind: "images", status: "pending", reason: "", warning: "", output: "", pages: 2, pages_total: null, pages_done: 0, pages_skipped: [] },
        { path: "extra.pdf", item_id: "extra", kind: "pdf", status: "pending", reason: "", warning: "", output: "", pages: 2, pages_total: null, pages_done: 0, pages_skipped: [] },
        { path: "v04.cbz", item_id: "v04", kind: "archive", status: "pending", reason: "", warning: "", output: "", pages: 2, pages_total: null, pages_done: 0, pages_skipped: [] },
        { path: "corrupt.cbz", item_id: "corrupt", kind: "archive", status: "pending", reason: "", warning: "", output: "", pages: 1, pages_total: null, pages_done: 0, pages_skipped: [] },
      ],
      warnings: ["v03.cbr was read as a .cbz; RAR archives are not written back."],
      ok: 0,
      skipped: 0,
      failed: 0,
      cancelled_items: 0,
      paused_items: 0,
      pages_skipped: 0,
      pending: 7,
      running: 0,
      done: false,
      cancelled: false,
      paused: false,
      pause_reason: "",
    };
    jobs.set(job_id, job);
    void runJob(job);
    return structuredClone(job);
  }
  const m = path.match(/^\/api\/job\/([^/]+)(\/cancel|\/resume)?$/);
  if (m) {
    const job = jobs.get(decodeURIComponent(m[1]));
    if (!job) throw { status: 404, body: "no such job" };
    if (m[2] === "/cancel") {
      job.cancelled = true;
      if (job.paused && job.done) {
        // Cancel settles a paused job: what it left is cancelled.
        for (const it of job.items) {
          if (it.status === "pending" || it.status === "paused") {
            if (it.status === "paused") job.paused_items--;
            else job.pending--;
            it.status = "cancelled";
            job.cancelled_items++;
          }
        }
        job.paused = false;
        job.pause_reason = "";
      }
    }
    if (m[2] === "/resume") {
      if (!job.paused || !job.done) throw { status: 409, body: '{"error":"not paused"}' };
      resumed.add(job.job_id);
      for (const it of job.items) {
        if (it.status === "paused") {
          it.status = "pending";
          it.reason = "";
          job.paused_items--;
          job.pending++;
        }
      }
      job.paused = false;
      job.pause_reason = "";
      job.done = false;
      void runJob(job);
    }
    return structuredClone(job);
  }
  throw { status: 404, body: `mock: no route for ${method} ${path}` };
}

// event.js unregisters through this second global BEFORE it invokes
// plugin:event|unlisten. Without it the unlisten throws, the first of React's
// StrictMode double-mounts keeps its listener, and every line arrives twice.
(window as unknown as { __TAURI_EVENT_PLUGIN_INTERNALS__: unknown }).__TAURI_EVENT_PLUGIN_INTERNALS__ = {
  unregisterListener(event: string, eventId: number) {
    listeners.get(event)?.delete(eventId);
    callbacks.delete(eventId);
  },
};

(window as unknown as { __TAURI_INTERNALS__: unknown }).__TAURI_INTERNALS__ = {
  metadata: {
    currentWindow: { label: "main" },
    currentWebview: { windowLabel: "main", label: "main" },
  },
  transformCallback(cb: Callback) {
    const id = nextId++;
    callbacks.set(id, cb);
    return id;
  },
  unregisterCallback(id: number) {
    callbacks.delete(id);
  },
  convertFileSrc(p: string) {
    return p;
  },
  async invoke(cmd: string, args: Record<string, unknown> = {}) {
    switch (cmd) {
      case "start_sidecar":
        setTimeout(() => emit("sidecar-log", "INFO:     Uvicorn running on http://127.0.0.1:8765"), 300);
        setTimeout(() => emit("sidecar-log", "INFO:     Application startup complete."), 900);
        return 8765;
      case "stop_sidecar":
      case "allow_output_dir":
        return undefined;
      case "frontend_log":
        // No terminal in a browser; the console is the nearest thing.
        console.error(`[ui:${String(args.level)}] ${String(args.message)}`);
        return undefined;
      case "api":
        return api(String(args.path), String(args.method), args.body as Record<string, unknown> | null);
      case "plugin:event|listen": {
        const event = String(args.event);
        const handler = Number(args.handler);
        if (!listeners.has(event)) listeners.set(event, new Set());
        listeners.get(event)!.add(handler);
        return handler;
      }
      case "plugin:event|unlisten": {
        listeners.get(String(args.event))?.delete(Number(args.eventId));
        return undefined;
      }
      case "plugin:dialog|open": {
        const o = (args.options ?? {}) as { directory?: boolean; multiple?: boolean };
        if (o.multiple) {
          return o.directory
            ? ["C:\\Manga\\series\\ch05"]
            : ["C:\\Manga\\series\\v01.cbz", "C:\\Manga\\series\\v02.cbz"];
        }
        return o.directory ? "C:\\Manga\\series" : "C:\\Manga\\chapter-01.cbz";
      }
      // @tauri-apps/api/path: Settings resolves the bundled sample page and
      // the app data folder through these two. BaseDirectory.Resource is 11,
      // AppLocalData is 15 -- the enum in path.js, not exported as strings.
      case "plugin:path|resolve_directory": {
        const dir = Number(args.directory);
        const base = dir === 11 ? "C:\\Program Files\\Komalingo" : "C:\\Users\\me\\AppData\\Local\\asia.komorebi.komalingo";
        return args.path ? `${base}\\${String(args.path)}` : base;
      }
      case "plugin:path|join":
        return (args.paths as string[]).join("\\");
      default:
        throw { status: 0, body: `mock: unknown command ${cmd}` };
    }
  },
};

console.info("[mock-tauri] runtime stubbed for browser preview");
