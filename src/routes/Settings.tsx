/**
 * Provider settings: base URL, API key, model. All three are configured here
 * and nowhere else.
 *
 * There is no default base URL and no default model in this file, in api.ts, or
 * in the sidecar. A default would be a credential baked into the shipped app,
 * and the user could not tell it was there. Empty fields are what "not
 * configured yet" looks like.
 *
 * The API key is optional and may legitimately stay empty -- a local llama.cpp
 * or Ollama server needs none, and requiring one would lock those users out.
 * Only the base URL and model are required to test.
 */

import { useEffect, useRef, useState } from "react";
import { appLocalDataDir, join, resolveResource } from "@tauri-apps/api/path";
import { Alert } from "../components/Alert";
import { Icon } from "../components/Icon";
import { ModelCombobox, type ModelComboboxHandle } from "../components/ModelCombobox";
import {
  api,
  describeError,
  displayPath,
  loadSettings,
  saveSettings,
  type CacheStats,
  type ModelInfo,
  type ProviderSettings,
} from "../lib/api";

const BYTES = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

/** 812.4 MB, 4 GB. Binary units, because the sidecar's cap is 4 * 1024**3. */
function formatBytes(n: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  // A no-break space: "812.5" and "MB" on two lines of a narrow card read as two values.
  return `${BYTES.format(n)} ${units[i]}`;
}

const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;

/**
 * Where the sample run reads from and writes to. Both ABSOLUTE.
 *
 * The sidecar resolves a relative path against its own working directory,
 * which under Tauri is wherever the app was launched from -- not the repo, and
 * not anywhere the user can see. The first version sent "fixtures/sample.png"
 * and "out/test", and the sidecar answered with a FileNotFoundError inside the
 * 500 envelope. The page is bundled as a resource (tauri.conf.json
 * bundle.resources) so it exists in a built app as well as under `tauri dev`;
 * the output goes under the app's own data folder, where a test run cannot
 * land in a directory the user did not choose.
 */
async function samplePaths(): Promise<{ src: string; dest: string }> {
  const [src, data] = await Promise.all([resolveResource("sample.png"), appLocalDataDir()]);
  return { src, dest: await join(data, "test") };
}

/** Which card a message belongs under. */
type Where = "provider" | "test" | "cache";

export default function Settings() {
  const [s, setS] = useState<ProviderSettings>(loadSettings);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [busy, setBusy] = useState("");
  const [showKey, setShowKey] = useState(false);
  // Two channels, deliberately: `error` renders the provider's own status and
  // body verbatim (AC-8), `note` is ours. Merging them is how a provider's
  // "model not found" becomes our "connection failed".
  const [error, setError] = useState<{ where: Where; text: string } | null>(null);
  // Each message names the card whose button produced it and renders there,
  // under that button: a test result that appeared in the Provider card
  // read as a reply to the wrong thing. `path`, when present, is its own
  // wrapped line: a Windows path is one unbreakable token, and inline in a
  // sentence it ran past the card's edge.
  const [note, setNote] = useState<{
    where: Where;
    tone: "success" | "info";
    text: string;
    path?: string;
  } | null>(null);
  const modelBox = useRef<ModelComboboxHandle>(null);
  // Shown in the card so the user knows where the test wrote, before running it.
  const [sample, setSample] = useState<{ src: string; dest: string } | null>(null);
  // null while the first read is in flight; the card says "Reading…" then.
  const [cache, setCache] = useState<CacheStats | null>(null);
  // Clearing is two presses: the first one asks, in place, and says what
  // goes. A browser confirm() would block the webview's event loop and could
  // not say how many of the pages hold the user's own corrections.
  const [confirming, setConfirming] = useState(false);
  const clearBtn = useRef<HTMLButtonElement>(null);
  const cancelBtn = useRef<HTMLButtonElement>(null);

  // Persist on every edit, so settings survive a restart without a Save button
  // the user can forget to press.
  useEffect(() => saveSettings(s), [s]);

  async function readCache() {
    try {
      setCache(await api.cache.stats());
    } catch (e) {
      setError({ where: "cache", text: describeError(e) });
    }
  }

  useEffect(() => {
    void readCache();
  }, []);

  // Focus lands on Cancel, the safe answer, when the question opens, and back
  // on the button that asked it when the question closes. In an effect, not
  // in the handlers: the button being focused is only mounted after the
  // render that swaps the two branches.
  const asked = useRef(false);
  useEffect(() => {
    if (confirming) {
      asked.current = true;
      cancelBtn.current?.focus();
    } else if (asked.current) {
      asked.current = false;
      clearBtn.current?.focus();
    }
  }, [confirming]);

  const cancelClear = () => setConfirming(false);

  async function clearCache() {
    setBusy("cache");
    setError(null);
    setNote(null);
    try {
      const r = await api.cache.clear();
      const kept = r.held
        ? ` ${plural(r.held, "page")} kept: a running job is still using them.`
        : "";
      setNote({
        where: "cache",
        tone: r.held ? "info" : "success",
        text: `Cleared ${plural(r.removed, "page")}, ${formatBytes(r.freed_bytes)} freed.${kept}`,
      });
    } catch (e) {
      setError({ where: "cache", text: describeError(e) });
    } finally {
      setConfirming(false);
      setBusy("");
      await readCache();
    }
  }

  useEffect(() => {
    let live = true;
    samplePaths()
      .then((p) => live && setSample(p))
      .catch(() => live && setSample(null));
    return () => {
      live = false;
    };
  }, []);

  const set = (k: keyof ProviderSettings) => (e: { target: { value: string } }) =>
    setS((prev) => ({ ...prev, [k]: e.target.value }));

  async function loadModels() {
    setBusy("models");
    setError(null);
    setNote(null);
    try {
      const r = await api.models({ base_url: s.base_url, api_key: s.api_key });
      setModels(r.models);
      if (r.models.length === 0) {
        setNote({ where: "provider", tone: "info", text: "The endpoint returned no models." });
      } else {
        setNote({ where: "provider", tone: "info", text: `${r.models.length} models loaded.` });
        // The next thing to do is pick one, so the list opens with focus in
        // the field: no second click to find out what arrived.
        modelBox.current?.open();
      }
    } catch (e) {
      setError({ where: "provider", text: describeError(e) });
    } finally {
      setBusy("");
    }
  }

  async function testSample() {
    setBusy("test");
    setError(null);
    setNote(null);
    try {
      // Resolved here, not read from state: the card may still be waiting on
      // the paths when the button is pressed, and a stale null would send
      // the sidecar nothing to open.
      const p = sample ?? (await samplePaths());
      const r = await api.translate({
        src_path: p.src,
        dest_dir: p.dest,
        settings: s,
      });
      setNote({
        where: "test",
        tone: "success",
        text: `OK — ${r.detections} regions detected, ${r.ocr_calls} OCR calls. Wrote:`,
        path: r.output,
      });
    } catch (e) {
      setError({ where: "test", text: describeError(e) });
    } finally {
      setBusy("");
    }
  }

  /** The card's messages, under the button that produced them. */
  function messages(where: Where) {
    return (
      <>
        {/* The provider's own status and body, unedited. See AC-8. */}
        {error?.where === where && <Alert tone="error">{error.text}</Alert>}
        {note?.where === where && (
          <Alert tone={note.tone}>
            {note.text}
            {note.path && <code className="alert-path">{displayPath(note.path)}</code>}
          </Alert>
        )}
      </>
    );
  }

  const ready = s.base_url.trim() !== "" && s.model.trim() !== "";

  return (
    <div className="view stack">
      <div className="view-head">
        <div>
          <h1>Settings</h1>
          <p className="sub">The model endpoint every translation goes through.</p>
        </div>
        {ready ? (
          <span className="pill ok">
            <Icon name="check" size={12} />
            Configured
          </span>
        ) : (
          <span className="pill skipped">
            <Icon name="alert-triangle" size={12} />
            Not configured
          </span>
        )}
      </div>

      <div className="settings-grid">
        <section className="card stack">
          <div className="card-head" style={{ marginBottom: 0 }}>
            <span className="icon-tile">
              <Icon name="sliders" />
            </span>
            <div>
              <h2>Provider</h2>
              <p className="sub">Any OpenAI-compatible endpoint. Saved as you type.</p>
            </div>
          </div>

          <div className="field">
            <label className="label" htmlFor="base-url">
              Base URL
            </label>
            <input
              id="base-url"
              className="input-path"
              value={s.base_url}
              onChange={set("base_url")}
              placeholder="http://localhost:8080/v1"
              spellCheck={false}
              autoComplete="off"
              aria-describedby="base-url-hint"
            />
            <span id="base-url-hint" className="hint">
              Up to and including <code>/v1</code>.
            </span>
          </div>

          <div className="field">
            <label className="label" htmlFor="api-key">
              API key
            </label>
            <div className="control">
              <input
                id="api-key"
                className="input-path"
                type={showKey ? "text" : "password"}
                value={s.api_key}
                onChange={set("api_key")}
                autoComplete="off"
                spellCheck={false}
                aria-describedby="api-key-hint"
              />
              <button
                type="button"
                className="btn icon"
                onClick={() => setShowKey((v) => !v)}
                aria-pressed={showKey}
              >
                <Icon name={showKey ? "eye-off" : "eye"} label={showKey ? "Hide key" : "Show key"} />
              </button>
            </div>
            <span id="api-key-hint" className="hint">
              Optional. Local servers usually need none. Stays on this machine.
            </span>
          </div>

          <div className="field">
            <label className="label" htmlFor="model">
              Model
            </label>
            <div className="control">
              {/* A combobox rather than a <select>: the list comes from the user's
                  own endpoint, and a select would make a model unreachable whenever
                  that endpoint refuses to enumerate. Typing always works; the list
                  filters as you type. */}
              <ModelCombobox
                ref={modelBox}
                id="model"
                value={s.model}
                onChange={(v) => setS((prev) => ({ ...prev, model: v }))}
                options={models}
                placeholder="type a model id, or load the list"
                describedBy="model-hint"
              />
              <button
                type="button"
                className="btn"
                onClick={loadModels}
                disabled={!s.base_url.trim() || busy !== ""}
              >
                {busy === "models" ? (
                  <Icon name="loader" className="spin" />
                ) : (
                  <Icon name="refresh" />
                )}
                {busy === "models" ? "Loading…" : "Load models"}
              </button>
            </div>
            <span className="hint" id="model-hint">
              A vision-capable model reads the page image; a text-only one is
              detected and reported at run time.
            </span>
          </div>

          {messages("provider")}
        </section>

        <div className="settings-side">
          <section className="card stack">
            <div className="card-head" style={{ marginBottom: 0 }}>
              <span className="icon-tile">
                <Icon name="zap" />
              </span>
              <div>
                <h2>Check it works</h2>
                <p className="sub">One bundled page, end to end.</p>
              </div>
            </div>
            <dl className="kv">
              <dt>Input</dt>
              <dd className="mono">{sample?.src ?? "bundled sample page"}</dd>
              <dt>Output</dt>
              <dd className="mono">{sample?.dest ?? "the app's data folder"}</dd>
            </dl>
            <button
              className="btn primary"
              onClick={testSample}
              disabled={!ready || busy !== ""}
            >
              {busy === "test" ? <Icon name="loader" className="spin" /> : <Icon name="play" />}
              {busy === "test" ? "Translating…" : "Test with sample image"}
            </button>
            {!ready && (
              <p className="hint">Needs a base URL and a model.</p>
            )}
            {messages("test")}
          </section>

          <section className="card stack" aria-busy={busy === "cache"}>
            <div className="card-head" style={{ marginBottom: 0 }}>
              <span className="icon-tile">
                <Icon name="database" />
              </span>
              <div>
                <h2>Page cache</h2>
                <p className="sub">Pages already read and translated, so a re-run skips them.</p>
              </div>
            </div>
            <dl className="kv">
              <dt>Size</dt>
              <dd className="num">
                {cache ? `${formatBytes(cache.bytes)} of ${formatBytes(cache.cap_bytes)}` : "Reading…"}
              </dd>
              <dt>Pages</dt>
              <dd className="num">
                {cache
                  ? `${cache.pages}${cache.edited_pages ? ` (${cache.edited_pages} with your corrections)` : ""}`
                  : "—"}
              </dd>
              {cache && (
                <>
                  <dt>Folder</dt>
                  <dd className="mono">{displayPath(cache.root)}</dd>
                </>
              )}
            </dl>

            {confirming ? (
              <div
                className="stack"
                role="group"
                aria-label="Confirm clearing the page cache"
                onKeyDown={(e) => e.key === "Escape" && busy === "" && cancelClear()}
              >
                <Alert tone="warn" title={`Delete ${plural(cache?.pages ?? 0, "cached page")}?`}>
                  Translated files in your output folders stay. Re-running an item reads and
                  translates it again, and its pages can’t be spot-fixed until then.
                  {cache?.edited_pages
                    ? ` ${plural(cache.edited_pages, "page")} with your corrections go too.`
                    : ""}
                </Alert>
                <div className="row">
                  <button
                    type="button"
                    className="btn danger"
                    onClick={clearCache}
                    disabled={busy !== ""}
                  >
                    {busy === "cache" ? <Icon name="loader" className="spin" /> : <Icon name="trash" />}
                    {busy === "cache" ? "Clearing…" : "Delete pages"}
                  </button>
                  <button
                    ref={cancelBtn}
                    type="button"
                    className="btn ghost"
                    onClick={cancelClear}
                    disabled={busy !== ""}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                ref={clearBtn}
                type="button"
                className="btn danger"
                onClick={() => {
                  setError(null);
                  setNote(null);
                  setConfirming(true);
                }}
                disabled={!cache || cache.pages === 0 || busy !== ""}
              >
                <Icon name="trash" />
                Clear cache…
              </button>
            )}
            {cache?.pages === 0 && !note && <p className="hint">Nothing cached yet.</p>}
            {messages("cache")}
          </section>
        </div>
      </div>
    </div>
  );
}
