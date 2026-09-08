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
