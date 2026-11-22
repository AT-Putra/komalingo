/**
 * First-run setup (plan Phase 4.4): with no provider configured, Translate
 * shows this instead of a warning that sends the user away to Settings.
 * Endpoint, then model, then an optional end-to-end test on the bundled
 * page; "Save and continue" writes the same settings Settings edits.
 *
 * Settings stays the place to change them later. Nothing here has a default
 * endpoint or model, for the reason Settings has none: a default would be a
 * credential baked into the app.
 */

import { useState } from "react";
import { ErrorAlert } from "./ErrorAlert";
import { Icon } from "./Icon";
import { ModelCombobox } from "./ModelCombobox";
import { Alert } from "./Alert";
import {
  api,
  describeError,
  loadSettings,
  providerConfigured,
  saveSettings,
  type ModelInfo,
} from "../lib/api";
import { samplePaths } from "../lib/sample";

export function SetupCard({
  onConfigured,
  onOpenSettings,
}: {
  onConfigured: () => void;
  onOpenSettings: () => void;
}) {
  const [s, setS] = useState(loadSettings);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [busy, setBusy] = useState<"" | "models" | "test">("");
  const [error, setError] = useState("");
  const [passed, setPassed] = useState("");
  const ready = providerConfigured(s);

  async function loadModels() {
    setBusy("models");
    setError("");
    try {
      const r = await api.models({ base_url: s.base_url, api_key: s.api_key });
      setModels(r.models);
      if (r.models.length === 0) setError("The endpoint answered, but listed no models. Type the model id instead.");
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy("");
    }
  }

  async function test() {
    setBusy("test");
    setError("");
    setPassed("");
    try {
      const p = await samplePaths();
      const r = await api.translate({ src_path: p.src, dest_dir: p.dest, settings: s });
      setPassed(`It works: ${r.detections} bubbles found and translated on the sample page.`);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy("");
    }
  }

  function save() {
    saveSettings({ ...loadSettings(), ...s });
    onConfigured();
  }

  /** What was typed here goes with the user to Settings, not lost. */
  function allSettings() {
    saveSettings({ ...loadSettings(), ...s });
    onOpenSettings();
  }

  const set = (k: "base_url" | "api_key") => (e: { target: { value: string } }) =>
    setS((prev) => ({ ...prev, [k]: e.target.value }));

  return (
    <section className="card stack setup" aria-labelledby="setup-title">
      <div className="card-head" style={{ marginBottom: 0 }}>
        <span className="icon-tile">
          <Icon name="zap" />
        </span>
        <div>
          <h2 id="setup-title">Set up a model</h2>
          <p className="sub">
            Komalingo translates through an OpenAI-compatible endpoint: a cloud provider, or a local
            llama.cpp or Ollama server. Three steps.
          </p>
        </div>
      </div>

      <ol className="setup-steps">
        <li>
          <span className="step-no" aria-hidden>
            1
          </span>
          <div className="stack-sm">
            <div className="field">
              <label className="label" htmlFor="setup-url">
                Endpoint
              </label>
              <input
                id="setup-url"
                className="input-path"
                value={s.base_url}
                onChange={set("base_url")}
                placeholder="http://localhost:8080/v1"
                spellCheck={false}
                autoComplete="off"
              />
              <span className="hint">The base URL, up to and including /v1.</span>
            </div>
            <div className="field">
              <label className="label" htmlFor="setup-key">
                API key
              </label>
              <input
                id="setup-key"
                className="input-path"
                type="password"
                value={s.api_key}
                onChange={set("api_key")}
                spellCheck={false}
                autoComplete="off"
              />
              <span className="hint">Optional: local servers usually need none. It stays on this machine.</span>
            </div>
          </div>
        </li>
        <li>
          <span className="step-no" aria-hidden>
            2
          </span>
          <div className="field" style={{ flex: 1 }}>
            <label className="label" htmlFor="setup-model">
              Model
            </label>
            <div className="control">
              <ModelCombobox
                id="setup-model"
                value={s.model}
                onChange={(v) => setS((prev) => ({ ...prev, model: v }))}
                options={models}
                placeholder="type a model id, or load the list"
              />
              <button
                type="button"
                className="btn"
                onClick={loadModels}
                disabled={!s.base_url.trim() || busy !== ""}
              >
                <Icon name={busy === "models" ? "loader" : "refresh"} className={busy === "models" ? "spin" : undefined} />
                Load models
              </button>
            </div>
            <span className="hint">A model that reads images translates with the page in view.</span>
          </div>
        </li>
        <li>
          <span className="step-no" aria-hidden>
            3
          </span>
          <div className="stack-sm" style={{ flex: 1 }}>
            <div className="row">
              <button type="button" className="btn" onClick={test} disabled={!ready || busy !== ""}>
                <Icon name={busy === "test" ? "loader" : "play"} className={busy === "test" ? "spin" : undefined} />
                {busy === "test" ? "Translating the sample…" : "Test with the sample page"}
              </button>
              <span className="hint">Optional, about half a minute: one bundled page, end to end.</span>
            </div>
            {passed && <Alert tone="success">{passed}</Alert>}
          </div>
        </li>
      </ol>

      <ErrorAlert error={error} />

      <div className="row end">
        <button type="button" className="btn ghost" onClick={allSettings} disabled={busy !== ""}>
          All settings
        </button>
        {/* Not while a test runs: the card unmounts on save, and the test's
            answer would land nowhere. */}
        <button type="button" className="btn primary" onClick={save} disabled={!ready || busy !== ""}>
          <Icon name="check" />
          Save and continue
        </button>
      </div>
    </section>
  );
}
