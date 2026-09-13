//! US-008: the host-side properties a successful `cargo build` does not prove.
//!
//! Compiling proves the spawn call type-checks. It says nothing about whether
//! each stdout LINE becomes exactly one event, whether the decode is UTF-8, or
//! whether the nonce differs per spawn. Those are the acceptance criteria, so
//! they are what this file drives -- against the real `classify` and
//! `new_nonce`, not against a restatement of them.
//!
//! Runs under `cargo test`, no window and no WebDriver. US-011's check_ipc
//! covers the same events end to end through a live app; this is the fallback
//! that keeps the criteria verifiable when the driver is not usable.

use manga_translator_lib::testing::{classify, new_nonce, Line};

/// One line, one event -- and the event carries the line's own fields.
#[test]
fn a_progress_line_becomes_one_progress_event() {
    let raw = br#"{"stage":"detect","item":"2 regions","page":1,"pct":10}"#;
    match classify(raw) {
        Some(Line::Progress(p)) => {
            assert_eq!(p.stage, "detect");
            assert_eq!(p.item, "2 regions");
            assert_eq!(p.page, 1);
            assert_eq!(p.pct, 10);
        }
        other => panic!("expected a progress event, got {:?}", other),
    }
}

/// The chapter bar's end: `total` rides on the progress line when the sidecar
/// could count the item's pages, and is absent when it could not (a compressed
/// tar). Absent must stay PROGRESS -- a missing field that failed the decode
/// would send every line of such a run to the log pane instead of the bar.
#[test]
fn a_progress_line_carries_the_page_count_when_the_sidecar_knows_it() {
    let counted = br#"{"stage":"ocr","item":"3 calls","page":2,"pct":25,"total":24}"#;
    match classify(counted) {
        Some(Line::Progress(p)) => {
            assert_eq!(p.total, Some(24));
            assert_eq!(p.page, 2);
        }
        other => panic!("expected a progress event, got {:?}", other),
    }
    let uncounted = br#"{"stage":"ocr","item":"3 calls","page":2,"pct":25}"#;
    match classify(uncounted) {
        Some(Line::Progress(p)) => assert_eq!(p.total, None),
        other => panic!("expected a progress event, got {:?}", other),
    }
}

/// The decode is UTF-8. A cp1252 read turns a Japanese filename into mojibake
/// in the progress bar, and the bytes below are the shortest proof of which
/// decoder ran: they are valid UTF-8 and nothing else.
#[test]
fn a_non_ascii_item_survives_the_decode() {
    let raw = r#"{"stage":"ocr","item":"第1話.png","page":1,"pct":25}"#.as_bytes();
    match classify(raw) {
        Some(Line::Progress(p)) => assert_eq!(p.item, "第1話.png"),
        other => panic!("expected a progress event, got {:?}", other),
    }
}

/// uvicorn's own lines are not progress. Forwarded, never dropped: the
/// sidecar's startup errors arrive on this same pipe, and a dropped line is a
/// silent failure at exactly the moment the user needs to see one.
#[test]
fn a_non_json_line_becomes_a_log_event_rather_than_vanishing() {
    match classify(b"INFO:     Uvicorn running on http://127.0.0.1:8756") {
        Some(Line::Log(text)) => assert!(text.contains("Uvicorn running")),
        other => panic!("expected a log event, got {:?}", other),
    }
}

/// Well-formed JSON that is not a progress record is still a log, not a
/// silently-dropped line and not a half-filled progress bar.
#[test]
fn json_that_is_not_progress_is_a_log() {
    match classify(br#"{"detail":"not found"}"#) {
        Some(Line::Log(_)) => {}
        other => panic!("expected a log event, got {:?}", other),
    }
}

/// A blank line is not an event. Without this the bar redraws on every
/// trailing newline the child writes.
#[test]
fn a_blank_line_emits_nothing() {
    assert!(classify(b"").is_none());
    assert!(classify(b"   \r\n").is_none());
}

/// Per SPAWN, not per process. A constant here would mean every install shares
/// one shutdown token, and any page the user visits could POST it.
#[test]
fn the_nonce_differs_every_time_and_is_not_guessable_in_length() {
    let a = new_nonce();
    let b = new_nonce();
    assert_ne!(a, b, "two spawns produced the same nonce");
    assert!(a.len() >= 32, "nonce is only {} chars", a.len());
}
