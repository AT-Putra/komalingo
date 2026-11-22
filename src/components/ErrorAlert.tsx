/**
 * An error in plain words first, the sidecar's own status and body after
 * (plan Phase 4.3).
 *
 * The raw text is what describeError produced -- "HTTP 502" and the body,
 * verbatim -- and it stays, under Details: AC-8's promise is that the
 * provider's own words reach the user, and a model name that is wrong is
 * only diagnosable from them. What changes is the first line: a title that
 * says what kind of failure it is, and the one thing to do next.
 */

import { Alert } from "./Alert";

export interface ExplainedError {
  title: string;
  next: string;
  detail: string;
}

/** The kinds of failure the sidecar names, in the user's words. */
export function explainError(text: string): ExplainedError {
  const m = /^HTTP (\d{3})\n\n([\s\S]*)$/.exec(text);
  if (!m) {
    // Status 0 (the request never reached the sidecar) or a UI-side reason.
    // Its first sentence is the title and the rest of the line the next step:
    // cut at a length, a long message lost its instruction into Details.
    const first = text.split("\n")[0];
    const split = /^(.{1,160}?[.!?])\s+(.+)$/s.exec(first);
    const title = split ? split[1] : first.length > 160 ? `${first.slice(0, 157)}…` : first;
    return {
      title: title || "Something went wrong",
      next: split ? split[2] : "",
      detail: text.includes("\n") || (!split && first.length > 160) ? text : "",
    };
  }
  const status = Number(m[1]);
  let kind = "";
  let message = "";
  // The provider's own status, inside a 502 the sidecar relays.
  let upstream = -1;
  try {
    const body = JSON.parse(m[2]) as Record<string, unknown>;
    if ("status" in body && "body" in body) {
      kind = "provider";
      upstream = typeof body.status === "number" ? body.status : -1;
    } else {
      kind = typeof body.kind === "string" ? body.kind : "";
      message = typeof body.error === "string" ? body.error : "";
    }
  } catch {
    // Not JSON: the detail carries it as it came.
  }
  const say = (title: string, next: string): ExplainedError => ({ title, next, detail: text });
  if (kind === "provider" || status === 502) return provider(upstream, say);
  // The sidecar's 400s are all settings it cannot use (_bad_settings_response).
  if (status === 400) return say("These settings can't be used", message || "Check the endpoint in Settings.");
  if (status === 404) {
    // A fixed next step per kind: the sidecar's message (under Details) is a
    // diagnosis, and several of them say nothing about what to do.
    if (kind === "input") return say("A file or folder was not found", message);
    if (kind === "placement") {
      return say("That run has no record of this page", "Run the chapter again, then open it from the Queue.");
    }
    if (kind === "cache") return say("That page is no longer in the cache", "Run the chapter again to bring it back.");
    if (kind === "raster") {
      return say("The edit is saved, but the page can't be redrawn here", "Run the chapter again to see it.");
    }
    if (kind === "translation") {
      return say("There is no translation of this page to edit", "Run the chapter in this language first.");
    }
    if (kind === "region") return say("That bubble can't be edited", "Pick another bubble.");
    return say("Not found", message);
  }
  if (status === 409) return say("Not right now", message);
  if (status === 422) return say("The request was not valid", message);
  if (status === 503) {
    if (kind === "network") return say("A model file could not be downloaded", "Check the internet connection, then try again.");
    if (kind === "checksum") return say("A model file is damaged", "Try again: it is downloaded afresh.");
    if (kind === "space") return say("The disk is full", "Free some disk space, then try again.");
    return say("Something the app needs is not available", message);
  }
  if (status >= 500) return say("Something went wrong in the sidecar", "The full error is in the Log (bottom right).");
  return say(`The request failed (HTTP ${status})`, message);
}

/** A provider failure, titled by the provider's own status (-1: not given). */
function provider(
  upstream: number,
  say: (title: string, next: string) => ExplainedError,
): ExplainedError {
  const code = upstream > 0 ? ` (HTTP ${upstream})` : "";
  if (upstream === 0) {
    return say("The model provider could not be reached", "Check the endpoint address in Settings, and that the server is running.");
  }
  if (upstream === 401 || upstream === 403) {
    return say(`The provider did not accept the API key${code}`, "Check the key in Settings.");
  }
  if (upstream === 402 || upstream === 429) {
    return say(`The provider is limiting requests or out of credit${code}`, "Wait a minute or check the account, then try again.");
  }
  if (upstream === 404) {
    return say(`The provider does not know that model or address${code}`, "Check the endpoint and the model in Settings.");
  }
  if (upstream >= 500) {
    return say(`The model provider is having trouble${code}`, "Try again in a few minutes.");
  }
  return say(`The model provider returned an error${code}`, "Check the endpoint, the key and the model in Settings, then try again.");
}

export function ErrorAlert({ error }: { error: string }) {
  if (!error) return null;
  const e = explainError(error);
  return (
    <Alert tone="error" title={e.title}>
      {e.next && <span>{e.next}</span>}
      {e.detail && (
        <details className="alert-details">
          <summary>Details</summary>
          <pre>{e.detail}</pre>
        </details>
      )}
    </Alert>
  );
}
