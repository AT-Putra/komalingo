//! The Tauri host: spawns the sidecar, streams its progress, proxies its errors.
//!
//! Three things here are load-bearing:
//!
//!   * The shutdown nonce is generated PER SPAWN, in this process, and handed
//!     to the child through its environment. It is never written to a file and
//!     never sent to the renderer. Any web page the user visits can POST to
//!     localhost; the nonce is what separates our shutdown from theirs.
//!   * Each sidecar stdout LINE becomes exactly one event. Tauri's shell plugin
//!     already splits on newlines and hands us Vec<u8>; we decode UTF-8
//!     ourselves rather than trusting a lossy default, because stage names and
//!     filenames are Japanese more often than not.
//!   * The error path carries the sidecar's own HTTP status and body to the
//!     renderer (AC-8). Replacing a 502 "model not found" with a Rust-side
//!     "request failed" is how a user ends up staring at a generic error with
//!     no idea their model name is wrong.

use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::{Emitter, Manager, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const PORT: u16 = 8756;

/// What the renderer gets back when the sidecar answers with an error.
///
/// status and body are the SIDECAR's, verbatim. See AC-8.
#[derive(Serialize)]
struct ApiError {
    status: u16,
    body: String,
}

impl ApiError {
    fn local(body: impl Into<String>) -> Self {
        // 0 means "never reached the sidecar" -- distinguishable in the UI from
        // any real HTTP status the sidecar could return.
        Self { status: 0, body: body.into() }
    }
}

/// The child handle and its nonce, for the lifetime of the app.
#[derive(Default)]
struct Sidecar {
    child: Mutex<Option<CommandChild>>,
    nonce: Mutex<String>,
}

/// A progress line from the sidecar's stdout. Mirrors pipeline.emit().
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Progress {
    pub stage: String,
    pub item: String,
    pub page: i64,
    pub pct: i64,
    /// The item's page count, when the sidecar could read it cheaply. Absent
    /// on a compressed tar, so it defaults rather than failing the whole line:
    /// a missing field here would turn every progress event into a log line.
    #[serde(default)]
    pub total: Option<i64>,
}

/// What one sidecar stdout line becomes.
#[derive(Debug)]
pub enum Line {
    Progress(Progress),
    Log(String),
}

/// One line in, at most one event out.
///
/// Decoded as UTF-8 explicitly -- stage names and filenames are Japanese more
/// often than not, and a cp1252 read turns them into mojibake in the progress
/// bar. from_utf8_lossy rather than a panicking decode: one mangled line should
/// not kill the reader task and freeze the bar at whatever it last showed.
///
/// A line that is not progress is forwarded as a log rather than dropped --
/// uvicorn writes its own lines, and the sidecar's startup errors arrive on
/// this same pipe.
pub fn classify(line: &[u8]) -> Option<Line> {
    let text = String::from_utf8_lossy(line).trim().to_string();
    if text.is_empty() {
        return None;
    }
    Some(match serde_json::from_str::<Progress>(&text) {
        Ok(p) => Line::Progress(p),
        Err(_) => Line::Log(text),
    })
}

/// A fresh nonce per spawn. Never written to a file, never sent to the renderer.
pub fn new_nonce() -> String {
    uuid::Uuid::new_v4().to_string()
}

fn spawn(app: &tauri::AppHandle) -> Result<(), String> {
    let state: State<Sidecar> = app.state();
    // The slot is held for the whole spawn, so two start_sidecar calls
    // arriving together cannot both find it empty and start two sidecars
    // for one port.
    let mut slot = state.child.lock().unwrap();
    if slot.is_some() {
        return Ok(());
    }

    let nonce = new_nonce();

    let (mut rx, child) = app
        .shell()
        .sidecar("sidecar")
        .map_err(|e| e.to_string())?
        // PYTHONIOENCODING is belt to main.py's braces: without it a cp1252
        // default kills the run the first time a stage name meets a
        // non-ASCII filename.
        .env("PYTHONIOENCODING", "utf-8")
        .env("MT_SHUTDOWN_NONCE", &nonce)
        .env("MT_PORT", PORT.to_string())
        // The sidecar exits when its stdin pipe closes -- which is what
        // happens to the pipe below when THIS process ends, however it ends.
        // The nonce cannot do that job: it dies with us. Before this, every
        // `tauri dev` restart left a sidecar holding 8756, the new one failed
        // to bind, and the UI talked to the orphan (sidecar/main.py,
        // watch_parent).
        .env("MT_EXIT_ON_STDIN_EOF", "1")
        .spawn()
        .map_err(|e| e.to_string())?;

    let pid = child.pid();
    *state.nonce.lock().unwrap() = nonce;
    *slot = Some(child);
    drop(slot);

    let handle = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => match classify(&line) {
                    Some(Line::Progress(p)) => {
                        let _ = handle.emit("sidecar-progress", p);
                    }
                    Some(Line::Log(text)) => {
                        let _ = handle.emit("sidecar-log", text);
                    }
                    None => {}
                },
                CommandEvent::Stderr(line) => {
                    let _ = handle.emit("sidecar-log", String::from_utf8_lossy(&line).to_string());
                }
                CommandEvent::Terminated(payload) => {
                    // Free the slot, if it still holds THIS child, so the next
                    // start_sidecar spawns a new one instead of returning Ok for
                    // a corpse. By pid: a stop+start pair may already have put
                    // a newer child there, and that one is not ours to drop.
                    {
                        let state: State<Sidecar> = handle.state();
                        let mut slot = state.child.lock().unwrap();
                        if slot.as_ref().map(|c| c.pid()) == Some(pid) {
                            slot.take();
                        }
                    }
                    let _ = handle.emit("sidecar-exit", payload.code);
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(())
}

/// The webview's errors, on this process's stderr -- which is the terminal
/// `tauri dev` was launched from. The webview's own console is not: a render
/// crash that only reached devtools left the terminal saying nothing while
/// the window went blank. main.tsx forwards here in dev builds only; the
/// level is a tag, not a filter.
#[tauri::command]
fn frontend_log(level: String, message: String) {
    eprintln!("[ui:{level}] {message}");
}

#[tauri::command]
async fn start_sidecar(app: tauri::AppHandle) -> Result<u16, String> {
    spawn(&app)?;
    Ok(PORT)
}

/// Proxy one request to the sidecar, preserving its status and body.
///
/// Every error the renderer can see is an ApiError carrying what the sidecar
/// actually said. This function must never invent a message of its own for a
/// response that reached it -- that is the whole of AC-8.
#[tauri::command]
async fn api(
    path: String,
    method: String,
    body: Option<serde_json::Value>,
) -> Result<serde_json::Value, ApiError> {
    let url = format!("http://127.0.0.1:{PORT}{path}");
    let client = reqwest::Client::new();
    let req = match method.as_str() {
        "POST" => client.post(&url).json(&body.unwrap_or(serde_json::Value::Null)),
        _ => client.get(&url),
    };

    let resp = req.send().await.map_err(|e| ApiError::local(e.to_string()))?;
    let status = resp.status().as_u16();
    let text = resp.text().await.map_err(|e| ApiError::local(e.to_string()))?;

    if !(200..300).contains(&status) {
        // The sidecar's own status and body, untouched.
        return Err(ApiError { status, body: text });
    }
    serde_json::from_str(&text).map_err(|e| ApiError::local(e.to_string()))
}

/// Let the webview read the pages under one output folder.
///
/// The asset protocol ships with an empty scope (tauri.conf.json) and this is
/// the only way it widens: the folder the user picked for this run, and its
/// subtree, because that is where pipeline._deliver puts every page. A static
/// `**` scope would have handed the webview the whole disk to load a picture
/// from a directory it already chose.
#[tauri::command]
async fn allow_output_dir(app: tauri::AppHandle, path: String) -> Result<(), String> {
    app.asset_protocol_scope()
        .allow_directory(&path, true)
        .map_err(|e| e.to_string())
}

/// Stop the sidecar this app started. Not called on app exit -- the process
/// ending closes the sidecar's stdin pipe, and the sidecar exits on that
/// (sidecar/main.py, watch_parent). Kept for an explicit restart action.
#[tauri::command]
async fn stop_sidecar(app: tauri::AppHandle) -> Result<(), String> {
    let state: State<Sidecar> = app.state();
    // Take the child and its nonce BEFORE the first await. When this ran
    // after the shutdown POST, a start_sidecar arriving during that await
    // found the slot still occupied, spawned nothing -- and then this killed
    // the only sidecar there was. React's StrictMode dev mount issued
    // exactly that start, stop, start sequence on every launch.
    let child = state.child.lock().unwrap().take();
    let nonce = std::mem::take(&mut *state.nonce.lock().unwrap());
    let Some(child) = child else {
        return Ok(());
    };
    // Ask politely first: the sidecar exits after answering, so an in-flight
    // page write lands instead of being truncated by a kill.
    let _ = reqwest::Client::new()
        .post(format!("http://127.0.0.1:{PORT}/api/shutdown"))
        .header("X-Shutdown-Nonce", nonce)
        .send()
        .await;
    // This ends the PyInstaller bootloader; the Python process under it ends
    // when `child` drops here and closes the stdin pipe. A kill alone never
    // reached that second process -- which is where the orphans came from.
    let _ = child.kill();
    Ok(())
}

/// The WebView profile folder under the identifier before the rename.
pub const OLD_IDENTIFIER: &str = "com.adita.mangatranslator";
/// Must match `identifier` in tauri.conf.json.
pub const IDENTIFIER: &str = "asia.komorebi.komalingo";

/// Move the pre-rename WebView profile into the new identifier's folder.
///
/// The app was MangaTranslator until 2026-09-13. Tauri keys the WebView's
/// profile -- localStorage, where the provider settings and the theme live --
/// on the identifier's folder under %LOCALAPPDATA%, so without this the first
/// launch after the rename opens with every setting blank. Moved, never
/// merged: an existing new folder is left alone, and a failed rename (a file
/// held open) is retried next launch. main.rs calls it before the builder, so
/// no WebView has the folder open yet. Returns whether it moved anything.
pub fn move_old_profile(base: &std::path::Path) -> bool {
    let new = base.join(IDENTIFIER);
    let old = base.join(OLD_IDENTIFIER);
    !new.exists() && old.is_dir() && std::fs::rename(&old, &new).is_ok()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(Sidecar::default())
        .invoke_handler(tauri::generate_handler![
            start_sidecar,
            stop_sidecar,
            api,
            allow_output_dir,
            frontend_log
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

/// The seam tests/host.rs drives. Named rather than exported at the root so it
/// is obvious at a glance that these are reachable from outside the crate on
/// purpose, not by accident.
pub mod testing {
    pub use super::{classify, new_nonce, Line, Progress};
}
