import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

async function boot() {
  // A plain browser under `npm run dev` gets the stubbed runtime, so every
  // view can be looked at without the sidecar. The condition is constant in a
  // production build and Vite drops the import with it.
  if (import.meta.env.DEV && !("__TAURI_INTERNALS__" in window)) {
    await import("./dev/mock-tauri");
  }
  ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

void boot();
