/**
 * Errors the UI could not handle, sent somewhere a person will see them.
 *
 * Always the console. In a dev build also the terminal, through the
 * `frontend_log` command: `tauri dev` inherits the Rust process's stderr and
 * the webview's console is a devtools pane nobody has open, so a render crash
 * used to leave the window blank and the terminal silent at the same time.
 * Production builds keep the console only -- there is no terminal to reach.
 */

import { invoke } from "@tauri-apps/api/core";

export function reportError(kind: string, error: unknown, extra = ""): void {
  const err = error instanceof Error ? error : new Error(String(error));
  console.error(`[${kind}]`, err, extra);
  if (!import.meta.env.DEV) return;
  const text = [`${kind}: ${err.name}: ${err.message}`, err.stack ?? "", extra.trim()]
    .filter(Boolean)
    .join("\n");
  // Fire and forget. A failed report must not become a second error.
  invoke("frontend_log", { level: "error", message: text }).catch(() => {});
}

/** Forward what no component caught: thrown outside React, or a promise nobody awaited. */
export function installGlobalReporting(): void {
  window.addEventListener("error", (e) => reportError("uncaught", e.error ?? e.message));
  window.addEventListener("unhandledrejection", (e) => reportError("unhandled rejection", e.reason));
}
