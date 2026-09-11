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
    return e.status === 0 ? e.body : `HTTP ${e.status}\n\n${e.body}`;
  }
  return String(e);
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

export interface PageRecord {
  page: number;
  page_hash: string;
  item_id: string;
  member: string;
  output: string;
  cached: boolean;
  detections: number;
  regions: Region[];
  fit_summary: {
    fit_compromised: number[];
    fit_failed: number[];
    retranslated: number[];
  };
  /** Present when the page cache is over its cap and could not evict. */
  cache_warning?: string | null;
  /** True when an edit for this page exists under a different model. */
  edit_on_other_model?: boolean;
  edited_region?: number;
}

export interface ItemResult {
  job_id: string;
  item_id: string;
  pages: PageRecord[];
  cache_warning: string | null;
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

  /** Populate the model dropdown from the user's own endpoint. */
  models: (s: Pick<ProviderSettings, "base_url" | "api_key">) => {
    const q = new URLSearchParams({ base_url: s.base_url, api_key: s.api_key });
    return call<{ models: ModelInfo[] }>(`/api/models?${q}`);
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
    lang?: string;
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
    lang?: string;
    settings?: ProviderSettings;
  }) => call<PageRecord>("/api/rerender", "POST", req),
};

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
