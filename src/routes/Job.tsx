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
 */

import { useEffect, useState } from "react";
import { api, describeError, type JobStatus } from "../lib/api";

const POLL_MS = 500;

export default function Job({ jobId, initial }: { jobId: string; initial: JobStatus }) {
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
  const finished = status.ok + status.skipped + status.failed;

  return (
    <section className="job">
      <h2>Job {status.job_id}</h2>
      {error && <pre className="error">{error}</pre>}
      <p>
        {finished} / {total} items · {status.ok} ok · {status.skipped} skipped ·{" "}
        {status.failed} failed
        {status.done ? " · done" : status.cancelled ? " · cancelling…" : ` · ${status.running} running`}
      </p>
      {status.warnings.map((w) => (
        <p key={w} className="warn">
          {w}
        </p>
      ))}
      {!status.done && (
        <button onClick={cancel} disabled={status.cancelled}>
          Cancel remaining items
        </button>
      )}
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Kind</th>
            <th>Status</th>
            <th>Pages</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {status.items.map((item) => (
            <tr key={item.item_id} className={item.status}>
              <td>{item.item_id}</td>
              <td>{item.kind}</td>
              <td>{item.status}</td>
              <td>{item.pages || ""}</td>
              <td>{item.reason || item.warning}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
