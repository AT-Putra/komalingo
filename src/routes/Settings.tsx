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

import { useEffect, useState } from "react";
import { Alert } from "../components/Alert";
import { Icon } from "../components/Icon";
import {
  api,
  describeError,
  loadSettings,
  saveSettings,
  type ModelInfo,
  type ProviderSettings,
} from "../lib/api";

export default function Settings() {
  const [s, setS] = useState<ProviderSettings>(loadSettings);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [busy, setBusy] = useState("");
  const [showKey, setShowKey] = useState(false);
  // Two channels, deliberately: `error` renders the provider's own status and
  // body verbatim (AC-8), `note` is ours. Merging them is how a provider's
  // "model not found" becomes our "connection failed".
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  // Persist on every edit, so settings survive a restart without a Save button
  // the user can forget to press.
  useEffect(() => saveSettings(s), [s]);

  const set = (k: keyof ProviderSettings) => (e: { target: { value: string } }) =>
    setS((prev) => ({ ...prev, [k]: e.target.value }));

  async function loadModels() {
    setBusy("models");
    setError("");
    setNote("");
    try {
      const r = await api.models({ base_url: s.base_url, api_key: s.api_key });
      setModels(r.models);
      if (r.models.length === 0) setNote("The endpoint returned no models.");
      else setNote(`${r.models.length} models loaded. Pick one in the Model field.`);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy("");
    }
  }

  async function testSample() {
    setBusy("test");
    setError("");
    setNote("");
    try {
      const r = await api.translate({
        src_path: "fixtures/sample.png",
        dest_dir: "out/test",
        settings: s,
      });
      setNote(
        `OK — ${r.detections} detected, ${r.ocr_calls} OCR calls, wrote ${r.output}`,
      );
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy("");
    }
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
              <input
                id="model"
                className="input-path"
                list="mt-models"
                value={s.model}
                onChange={set("model")}
                placeholder="type a model id, or load the list"
                spellCheck={false}
                autoComplete="off"
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
            {/* A datalist rather than a <select>: the list comes from the user's own
                endpoint, and a select would make a model unreachable whenever that
                endpoint refuses to enumerate. Typing always works. */}
            <datalist id="mt-models">
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.owned_by ?? ""}
                </option>
              ))}
            </datalist>
            <span className="hint">
              A vision-capable model reads the page image; a text-only one is
              detected and reported at run time.
            </span>
          </div>

          {/* The provider's own status and body, unedited. See AC-8. */}
          {error && <Alert tone="error">{error}</Alert>}
          {note && <Alert tone={note.startsWith("OK") ? "success" : "info"}>{note}</Alert>}
        </section>

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
            <dd className="mono">fixtures/sample.png</dd>
            <dt>Output</dt>
            <dd className="mono">out/test</dd>
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
        </section>
      </div>
    </div>
  );
}
