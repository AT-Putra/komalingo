/**
 * AC-7: the queue view. One row per item, its status and its reason.
 *
 * Polled, not pushed. The sidecar's stdout carries item_start / item_done
 * for the progress bar, but the per-item REASON -- why notes.txt was skipped,
 * which rule refused slip.cbz -- lives in the job's status snapshot, and a
 * snapshot every half second is cheaper to get right than reconstructing
 * the table from a stream of events. Polling stops when the job says done.
 *
 * The job's warnings are shown once, above the table, because that is the
 * scope AC-6 gives the cbr->cbz warning: once per job, not once per row.
 *
 * Status is never colour alone: every pill carries an icon and the word.
 */

import { useEffect, useState, type CSSProperties } from "react";
import { Alert } from "../components/Alert";
import { Icon, type IconName } from "../components/Icon";
import { ProgressBar } from "../components/Progress";
import { api, describeError, type JobItem, type JobStatus } from "../lib/api";

const POLL_MS = 500;

const PILL: Record<JobItem["status"], { icon: IconName; text: string }> = {
  pending: { icon: "clock", text: "Pending" },
  ok: { icon: "check", text: "Done" },
  skipped: { icon: "skip-forward", text: "Skipped" },
  failed: { icon: "alert-circle", text: "Failed" },
  cancelled: { icon: "ban", text: "Cancelled" },
};

function StatusPill({ status, running }: { status: JobItem["status"]; running: boolean }) {
  if (running) {
    return (
      <span className="pill running">
        <Icon name="loader" size={12} />
        Running
      </span>
    );
  }
  const p = PILL[status];
  return (
    <span className={`pill ${status}`}>
      <Icon name={p.icon} size={12} />
      {p.text}
    </span>
  );
}

export default function Job({
  jobId,
  initial,
  runningItems,
}: {
  jobId: string;
  initial: JobStatus;
  /** Item ids between an item_start and its item_done, from the event stream. */
  runningItems: Set<string>;
}) {
  const [status, setStatus] = useState<JobStatus>(initial);
  const [error, setError] = useState("");

  useEffect(() => {
    if (status.done) return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api.job.status(jobId);
        setStatus(fresh);
        if (fresh.done) clearInterval(timer);
      } catch (e) {
        setError(describeError(e));
        clearInterval(timer);
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [jobId, status.done]);

  async function cancel() {
    try {
      setStatus(await api.job.cancel(jobId));
    } catch (e) {
      setError(describeError(e));
    }
  }

  const total = status.items.length;
  const finished = status.ok + status.skipped + status.failed + status.cancelled_items;
  const state = status.done ? "done" : status.cancelled ? "cancelling" : "running";

  return (
    <div className="view stack">
      <div className="view-head">
        <div>
          <h1>Queue</h1>
          <p className="sub mono">{status.job_id}</p>
        </div>
        <div className="row">
          {state === "running" && (
            <span className="pill running">
              <Icon name="loader" size={12} />
              {status.running} running
            </span>
          )}
          {state === "cancelling" && (
            <span className="pill skipped">
              <Icon name="loader" size={12} />
              Cancelling…
            </span>
          )}
          {state === "done" && (
            <span className="pill ok">
              <Icon name="check" size={12} />
              Done
            </span>
          )}
          {!status.done && (
            <button className="btn danger sm" onClick={cancel} disabled={status.cancelled}>
              <Icon name="x" size={14} />
              Cancel remaining
            </button>
          )}
        </div>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {status.warnings.map((w) => (
        <Alert key={w} tone="warn">
          {w}
        </Alert>
      ))}

      <section className="card stack">
        <ProgressBar
          label="Items finished"
          value={finished}
          max={total}
          showValue
        />
        <div className="stats stagger">
          <div className="stat" style={{ "--i": 0 } as CSSProperties}>
            <div className="k">Finished</div>
            <div className="v">
              {finished}
              <span className="faint" style={{ fontSize: "0.9rem" }}>
                {" "}
                / {total}
              </span>
            </div>
          </div>
          <div className="stat ok" style={{ "--i": 1 } as CSSProperties}>
            <div className="k">OK</div>
            <div className="v">{status.ok}</div>
          </div>
          <div className="stat skipped" style={{ "--i": 2 } as CSSProperties}>
            <div className="k">Skipped</div>
            <div className="v">{status.skipped}</div>
          </div>
          <div className="stat failed" style={{ "--i": 3 } as CSSProperties}>
            <div className="k">Failed</div>
            <div className="v">{status.failed}</div>
          </div>
          {status.cancelled_items > 0 && (
            <div className="stat" style={{ "--i": 4 } as CSSProperties}>
              <div className="k">Cancelled</div>
              <div className="v">{status.cancelled_items}</div>
            </div>
          )}
        </div>
      </section>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th>Kind</th>
              <th>Status</th>
              <th className="num">Pages</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody className="stagger">
            {status.items.map((item, i) => (
              <tr
                key={item.item_id}
                className={item.status}
                style={{ "--i": i } as CSSProperties}
              >
                <td className="id">{item.item_id}</td>
                <td className="muted">{item.kind}</td>
                <td>
                  <StatusPill
                    status={item.status}
                    running={item.status === "pending" && runningItems.has(item.item_id)}
                  />
                </td>
                <td className="num">{item.pages || ""}</td>
                <td className="reason">{item.reason || item.warning}</td>
              </tr>
            ))}
            {status.items.length === 0 && (
              <tr>
                <td colSpan={5} className="faint" style={{ textAlign: "center" }}>
                  Nothing in the folder the queue could take.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
