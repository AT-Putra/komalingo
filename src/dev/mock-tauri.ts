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

import type { ItemResult, JobStatus, PageRecord, Region } from "../lib/api";

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

const jobs = new Map<string, JobStatus>();

async function runJob(job: JobStatus) {
  for (const item of job.items) {
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
    job.pending--;
    job.running++;
    emit("sidecar-progress", { stage: "item_start", item: item.item_id, page: 0, pct: 0 });
    await runPages(item.item_id, item.pages, 120);
    job.running--;
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
  if (path === "/api/item") {
    const job_id = String(body?.job_id);
    const item_id = "chapter-01";
    emit("sidecar-log", `INFO opening ${body?.src_path}`);
    await sleep(600);
    await runPages(item_id, 3, 700);
    const result: ItemResult = {
      job_id,
      item_id,
      pages: [1, 2, 3].map((n) => fakePage(item_id, n)),
      cache_warning: null,
    };
    return result;
  }
  if (path === "/api/rerender") {
    await sleep(700);
    const page = fakePage(String(body?.item_id), Number(body?.ordinal));
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
  if (path === "/api/job" && method === "POST") {
    const job_id = String(body?.job_id);
    const job: JobStatus = {
      job_id,
      items: [
        { path: "v01.cbz", item_id: "v01", kind: "archive", status: "pending", reason: "", warning: "", output: "", pages: 4 },
        { path: "v02.cbz", item_id: "v02", kind: "archive", status: "pending", reason: "", warning: "", output: "", pages: 3 },
        { path: "notes.txt", item_id: "notes", kind: "unsupported", status: "pending", reason: "", warning: "", output: "", pages: 0 },
        { path: "extra.pdf", item_id: "extra", kind: "pdf", status: "pending", reason: "", warning: "", output: "", pages: 2 },
        { path: "corrupt.cbz", item_id: "corrupt", kind: "archive", status: "pending", reason: "", warning: "", output: "", pages: 1 },
      ],
      warnings: ["v03.cbr was read as a .cbz; RAR archives are not written back."],
      ok: 0,
      skipped: 0,
      failed: 0,
      cancelled_items: 0,
      pending: 5,
      running: 0,
      done: false,
      cancelled: false,
    };
    jobs.set(job_id, job);
    void runJob(job);
    return structuredClone(job);
  }
  const m = path.match(/^\/api\/job\/([^/]+)(\/cancel)?$/);
  if (m) {
    const job = jobs.get(decodeURIComponent(m[1]));
    if (!job) throw { status: 404, body: "no such job" };
    if (m[2]) job.cancelled = true;
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
        const o = (args.options ?? {}) as { directory?: boolean };
        return o.directory ? "C:\\Manga\\series" : "C:\\Manga\\chapter-01.cbz";
      }
      // @tauri-apps/api/path: Settings resolves the bundled sample page and
      // the app data folder through these two. BaseDirectory.Resource is 11,
      // AppLocalData is 15 -- the enum in path.js, not exported as strings.
      case "plugin:path|resolve_directory": {
        const dir = Number(args.directory);
        const base = dir === 11 ? "C:\\Program Files\\MangaTranslator" : "C:\\Users\\me\\AppData\\Local\\com.adita.mangatranslator";
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
