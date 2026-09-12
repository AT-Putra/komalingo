import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { installGlobalReporting, reportError } from "./lib/report";

/**
 * index.html paints a splash before this module has even loaded -- inline
 * CSS, no JS -- so the window is never a blank page while Vite serves the
 * module graph or the bundle evaluates. Once React has committed its first
 * frame the splash fades and goes. If boot itself fails, the splash is the
 * only thing on screen, so the error goes there.
 */
function splash(): HTMLElement | null {
  return document.getElementById("splash");
}

function dismissSplash() {
  const el = splash();
  if (!el) return;
  el.classList.add("out");
  el.addEventListener("transitionend", () => el.remove(), { once: true });
  // Reduced motion, or a transition that never fires: gone anyway.
  setTimeout(() => el.remove(), 400);
}

function failSplash(e: unknown) {
  const el = splash();
  if (!el) return;
  el.removeAttribute("aria-busy");
  el.querySelector(".splash-bar")?.remove();
  const text = el.querySelector(".splash-text");
  if (text) text.textContent = "The UI failed to start.";
  const pre = document.createElement("pre");
  pre.className = "splash-error";
  pre.textContent = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
  el.appendChild(pre);
}

async function boot() {
  installGlobalReporting();
  // A plain browser under `npm run dev` gets the stubbed runtime, so every
  // view can be looked at without the sidecar. The condition is constant in a
  // production build and Vite drops the import with it.
  if (import.meta.env.DEV && !("__TAURI_INTERNALS__" in window)) {
    await import("./dev/mock-tauri");
  }
  ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
      <ErrorBoundary scope="The app" full>
        <App />
      </ErrorBoundary>
    </React.StrictMode>,
  );
  // After the first commit, not before render(): the shell is on screen.
  requestAnimationFrame(dismissSplash);
}

boot().catch((e) => {
  reportError("boot", e);
  failSplash(e);
});
