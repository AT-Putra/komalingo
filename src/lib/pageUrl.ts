import { convertFileSrc } from "@tauri-apps/api/core";

/**
 * A local file path as something the webview will load.
 *
 * Through the asset protocol, which the Rust side opened for this run's
 * output folder (allow_output_dir) before the job was started. The sidecar
 * hands paths back \\?\-prefixed (atomic.long_path); the prefix is for Win32,
 * not for a URL, so it comes off first. A data: URL (the dev mock) passes
 * through untouched.
 *
 * `bust` adds a query string: a re-render or a retry writes to the SAME path,
 * and without it the webview shows the old image and the user concludes
 * nothing happened. Never on a data: URL, which a query would corrupt.
 */
export function pageUrl(p: string, bust?: string | number): string {
  if (p.startsWith("data:")) return p;
  const plain = p.startsWith("\\\\?\\UNC\\")
    ? "\\\\" + p.slice(8)
    : p.replace(/^\\\\\?\\/, "");
  const url = convertFileSrc(plain);
  return bust === undefined ? url : `${url}?v=${bust}`;
}
