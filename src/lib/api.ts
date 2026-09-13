/**
 * The typed IPC client. Every call to the sidecar goes through here.
 *
 * ApiError carries the sidecar's own HTTP status and body (AC-8). The Rust side
 * preserves them; this file preserves them again rather than folding them into
 * an Error message string, because the Settings page renders the status and the
 * body verbatim. A user whose model name is wrong needs to read the provider's
 * "model not found", not our "connection failed".
 *
 * status === 0 means the request never reached the sidecar. Distinguishable in
 * the UI from any real HTTP status the sidecar could return.
 */

import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

export interface ApiError {
  status: number;
  body: string;
}

export function isApiError(e: unknown): e is ApiError {
  return typeof e === "object" && e !== null && "status" in e && "body" in e;
}

/** What the reader sees when a call fails. Status and body, never a synonym. */
export function describeError(e: unknown): string {
  if (isApiError(e)) {
    const text = e.status === 0 ? e.body : `HTTP ${e.status}\n\n${e.body}`;
    // The sidecar's 500 envelope names the exception class and, by design,
    // nothing else; the traceback went to its stderr, which is the Log
    // drawer. Say so, or the one place the answer is stays unopened.
    return isInternal(e.body) ? `${text}\n\nThe full traceback is in the Log (bottom right).` : text;
  }
  return String(e);
}

/**
 * A path as a person reads it. The sidecar opens and writes through Windows
 * long-path names, so the paths it reports come back as `\\?\C:\...`; the
 * prefix is an implementation detail of atomic.long_path, not something to
 * put in front of a user. UNC keeps its two leading slashes.
 */
export function displayPath(p: string): string {
  if (p.startsWith("\\\\?\\UNC\\")) return "\\\\" + p.slice(8);
  if (p.startsWith("\\\\?\\")) return p.slice(4);
  return p;
}

function isInternal(body: string): boolean {
  try {
    return (JSON.parse(body) as { kind?: unknown }).kind === "internal";
  } catch {
    return false;
  }
}

export interface ProviderSettings {
  base_url: string;
  api_key: string; // optional, may be empty: local servers often need none
  model: string;
}

export interface Progress {
  stage: string;
  item: string;
  page: number;
  pct: number;
  /** Pages in the item being run, when the sidecar could count them cheaply.
   *  Absent for a compressed tar, where the count costs a second decompression
   *  (sidecar/containers/archive.expected_pages). */
  total?: number;
  /** The item a page stage belongs to; `item` there is the stage's detail.
   *  Absent on item_start/item_done, whose `item` is the id. */
  item_id?: string | null;
}

export interface TranslateResult {
  page: number;
  output: string;
  detections: number;
  ocr_calls: number;
  inpaint_calls: number;
  pixels_changed_in_polygon: Record<string, number>;
}

/**
 * One detected region as regions.json carries it.
 *
 * `fit_compromised` and `fit_failed` are REPORTING fields, recomputed by the
 * typesetter on every render. The editor sorts on them and never writes them
 * back: shortening an edit clears the flag by re-rendering, and a UI that
 * cached the old value would keep highlighting a bubble that is now fine.
 */
export interface Region {
  id: number;
  polygon: [number, number][];
  /**
   * Phase 2b: the bubble interior the English was actually laid into, or
   * null when the typesetter declined one and used `polygon`. Derived on
   * every render like the fit flags. Drawn and hit-tested in preference to
   * `polygon`, because that is where the English now is.
   */
  room?: [number, number][] | null;
  text: string | null; // the Japanese source; null means not yet OCR'd
  translation: string;
  typeset: string;
  fit_compromised: boolean;
  fit_failed: boolean;
  fit_reason?: string;
  retranslated?: boolean;
  edited?: boolean;
}

/**
 * A region taken off the page before it was erased: the art under it is left
 * as drawn. `editable` is the vision model's null -- a call the user can
 * overrule by typing a translation; OCR's punctuation-only set-asides are not.
 */
export interface DismissedRegion {
  id: number;
  polygon: [number, number][];
  /** What the OCR read there. */
  text: string | null;
  reason: string;
  editable: boolean;
}

export interface PageRecord {
  page: number;
  page_hash: string;
  item_id: string;
  member: string;
  output: string;
  cached: boolean;
  detections: number;
  regions: Region[];
  /** Off the page, left as drawn. The editor lists the editable ones. */
  dismissed?: DismissedRegion[];
  fit_summary: {
    fit_compromised: number[];
    fit_failed: number[];
    retranslated: number[];
  };
  /** Present when the page cache is over its cap and could not evict. */
  cache_warning?: string | null;
  /** Set by /api/translate: see ItemResult.vision_warning. */
  vision_warning?: string;
  /** True when an edit for this page exists under a different model. */
  edit_on_other_model?: boolean;
  edited_region?: number;
  /**
   * Set by /api/rerender: the loose page carries the edit and the item's
   * archive does not yet. `repack` is the background rebuild that closes the
   * gap -- poll `api.repackStatus` while it reads pending or running. Null
   * when the sidecar has no record of where the item came from (a job run
   * before the placement carried it): re-running the item rebuilds it.
   */
  archive_stale?: boolean;
  repack?: RepackStatus | null;
}

/** Where the archive rebuild after an edit has got to. */
export interface RepackStatus {
  status: "idle" | "pending" | "running" | "done" | "failed";
  /** The rebuilt archive's path once `done`. */
  archive: string;
  /** Why, once `failed`. */
  error: string;
  /** Edits scheduled and repacks run, for the record. */
  edits: number;
  repacks: number;
}

export interface ItemResult {
  job_id: string;
  item_id: string;
  pages: PageRecord[];
  cache_warning: string | null;
  /**
   * Non-empty when the vision probe found the model text-only (every page
   * was translated without its image) or could not run (the reason says
   * which). The batch view carries the same sentence in JobStatus.warnings;
   * this is the single-file flow's copy of it.
   */
  vision_warning?: string;
}

/** One row of AC-7's queue: what became of one file in the folder. */
export interface JobItem {
  path: string;
  item_id: string;
  kind: "archive" | "pdf" | "image" | "unsupported";
  status: "pending" | "ok" | "skipped" | "failed" | "cancelled";
  /** Why it was skipped or failed, in the user's words. Empty when ok. */
  reason: string;
  /** A per-job warning this item raised first (cbr->cbz). */
  warning: string;
  output: string;
  pages: number;
}

/** The job's status snapshot, as job.Job.status() returns it. */
export interface JobStatus {
  job_id: string;
  items: JobItem[];
  /** Once per job, never once per item. */
  warnings: string[];
  ok: number;
  skipped: number;
  failed: number;
  /** AC-13: items stopped by the user at a page boundary, nothing partial left. */
  cancelled_items: number;
  pending: number;
  running: number;
  done: boolean;
  cancelled: boolean;
}

/** The page cache as cache.stats() reports it. */
export interface CacheStats {
  root: string;
  bytes: number;
  pages: number;
  /** Pages holding a spot-fix correction; clearing drops those too. */
  edited_pages: number;
  cap_bytes: number;
}

/** What cache.clear() removed and what it had to leave. */
export interface CacheClearResult {
  removed: number;
  /** Pages a running job holds, or that the OS would not let go of. */
  held: number;
  freed_bytes: number;
  /** What the cache holds after the clear. */
  bytes: number;
}

async function call<T>(
  path: string,
  method: "GET" | "POST" = "GET",
  body?: unknown,
): Promise<T> {
  return invoke<T>("api", { path, method, body: body ?? null });
}

export const api = {
  start: () => invoke<number>("start_sidecar"),
  stop: () => invoke<void>("stop_sidecar"),

  health: () => call<{ status: string; pid: number }>("/api/health"),

  /** Let the editor's canvas load pages from this folder (asset protocol). */
  allowOutputDir: (path: string) => invoke<void>("allow_output_dir", { path }),

  /** Populate the model dropdown from the user's own endpoint. */
  models: async (s: Pick<ProviderSettings, "base_url" | "api_key">) => {
    const q = new URLSearchParams({ base_url: s.base_url, api_key: s.api_key });
    const r = await call<{ models: unknown }>(`/api/models?${q}`);
    // Normalised HERE, at the boundary, so no component ever reads `.id` off
    // something that is not an object. The sidecar sends {id, owned_by}
    // objects; a bare string is still accepted as an id, and anything else
    // is dropped -- a list entry the UI cannot name is not worth a blank
    // window, which is what the first mismatch produced.
    const models: ModelInfo[] = [];
    for (const m of Array.isArray(r.models) ? r.models : []) {
      if (typeof m === "string" && m) models.push({ id: m });
      else if (m && typeof m === "object" && typeof (m as ModelInfo).id === "string" && (m as ModelInfo).id) {
        const owner = (m as ModelInfo).owned_by;
        models.push({ id: (m as ModelInfo).id, owned_by: typeof owner === "string" && owner ? owner : undefined });
      }
    }
    return { models };
  },

  translate: (req: {
    src_path: string;
    dest_dir: string;
    page?: number;
    settings?: ProviderSettings;
  }) => call<TranslateResult>("/api/translate", "POST", req),

  /** Every page of one CBZ, through the page cache. */
  item: (req: {
    src_path: string;
    dest_dir: string;
    job_id: string;
    item_id?: string;
    lang?: Target;
    /** The language the pages are written in: which OCR reads them. Phase 4. */
    source?: Source;
    settings?: ProviderSettings;
  }) => call<ItemResult>("/api/item", "POST", req),

  /**
   * AC-10: one region's text changes, that page alone is re-drawn.
   *
   * The page is addressed by (item_id, ordinal), never by page hash. Two
   * byte-identical pages in an archive share a hash, and editing one must not
   * edit the other.
   */
  rerender: (req: {
    job_id: string;
    item_id: string;
    ordinal: number;
    region_id: number;
    text: string;
    dest_dir: string;
    lang?: Target;
    settings?: ProviderSettings;
  }) => call<PageRecord>("/api/rerender", "POST", req),

  /** The background archive rebuild an edit scheduled. See PageRecord.repack. */
  repackStatus: (jobId: string, itemId: string) =>
    call<RepackStatus>(
      `/api/repack?job_id=${encodeURIComponent(jobId)}&item_id=${encodeURIComponent(itemId)}`,
    ),

  /** The page cache: how big, and a clear that keeps running jobs' pages. */
  cache: {
    stats: () => call<CacheStats>("/api/cache"),
    clear: () => call<CacheClearResult>("/api/cache/clear", "POST"),
  },

  /** AC-7: a folder through the queue. `start` answers at once; poll `status`. */
  job: {
    start: (req: {
      job_id: string;
      dest_dir: string;
      dir?: string;
      paths?: string[];
      lang?: Target;
      source?: Source;
      settings?: ProviderSettings;
    }) => call<JobStatus>("/api/job", "POST", req),
    status: (jobId: string) => call<JobStatus>(`/api/job/${encodeURIComponent(jobId)}`),
    /** Items not yet started are skipped; a running item finishes (Phase 9 stops it). */
    cancel: (jobId: string) =>
      call<JobStatus>(`/api/job/${encodeURIComponent(jobId)}/cancel`, "POST"),
  },
};

export type Source = "ja" | "zh" | "ko";
export const SOURCES: { value: Source; label: string }[] = [
  { value: "ja", label: "Japanese" },
  { value: "zh", label: "Chinese" },
  { value: "ko", label: "Korean" },
];
/** The language the reader wants. Phase 5 adds Indonesian (AC-4). */
export type Target = "en" | "id";
export const TARGETS: { value: Target; label: string }[] = [
  { value: "en", label: "English" },
  { value: "id", label: "Indonesian" },
];

export interface ModelInfo {
  id: string;
  owned_by?: string;
}

/** One sidecar stdout line, one callback. Returns the unlisten function. */
export function onProgress(fn: (p: Progress) => void): Promise<UnlistenFn> {
  return listen<Progress>("sidecar-progress", (e) => fn(e.payload));
}

export function onLog(fn: (line: string) => void): Promise<UnlistenFn> {
  return listen<string>("sidecar-log", (e) => fn(e.payload));
}

/** The sidecar THIS app spawned has exited; `code` is null when killed. */
export function onExit(fn: (code: number | null) => void): Promise<UnlistenFn> {
  return listen<number | null>("sidecar-exit", (e) => fn(e.payload));
}

const KEY = "mt.settings";

/**
 * Settings persist across restarts. localStorage rather than a Rust-side store
 * because these are per-user UI preferences, and the API key never leaves this
 * machine either way.
 *
 * ponytail: the key sits in localStorage in plaintext. Ceiling: anything with
 * access to the user's profile can read it, same as a config file. Upgrade
 * path: Windows DPAPI via a Rust command if the threat model ever includes
 * local attackers.
 */
export function loadSettings(): ProviderSettings {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return { base_url: "", api_key: "", model: "", ...JSON.parse(raw) };
  } catch {
    // Corrupt JSON should not blank the Settings page.
  }
  // No defaults. An empty base URL is what "not configured yet" looks like;
  // a default here would be a credential baked into the shipped app.
  return { base_url: "", api_key: "", model: "" };
}

export function saveSettings(s: ProviderSettings): void {
  localStorage.setItem(KEY, JSON.stringify(s));
}
