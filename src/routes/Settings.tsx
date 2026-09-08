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
    <section className="settings">
      <h1>Provider</h1>

      <label>
        Base URL
        <input
          value={s.base_url}
          onChange={set("base_url")}
          placeholder="http://localhost:8080/v1"
          spellCheck={false}
        />
      </label>

      <label>
        API key <span className="hint">optional — local servers often need none</span>
        <input
          type="password"
          value={s.api_key}
          onChange={set("api_key")}
          autoComplete="off"
          spellCheck={false}
        />
      </label>

      <label>
        Model
        <input
          list="mt-models"
          value={s.model}
          onChange={set("model")}
          placeholder="type, or load the list"
          spellCheck={false}
        />
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
      </label>

      <div className="row">
        <button onClick={loadModels} disabled={!s.base_url.trim() || busy !== ""}>
          {busy === "models" ? "Loading…" : "Load models"}
        </button>
        <button onClick={testSample} disabled={!ready || busy !== ""}>
          {busy === "test" ? "Translating…" : "Test with sample image"}
        </button>
      </div>

      {/* The provider's own status and body, unedited. See AC-8. */}
      {error && <pre className="error">{error}</pre>}
      {note && <p className="note">{note}</p>}
    </section>
  );
}
