/**
 * The two progress widgets, both driven by pipeline.emit()'s line.
 *
 * STAGES mirrors sidecar/pipeline.py and is a contract there too: check_ipc
 * asserts the names in order. The bar draws one segment per stage, which is
 * why the pipeline emits one line per stage and not one per sub-step.
 *
 * `item_start` / `item_done` are the job runner's bracketing lines, not
 * stages. They show up as "nothing yet" and "everything" on the track.
 */

import { Icon } from "./Icon";

export const STAGES = ["detect", "ocr", "translate", "inpaint", "render", "encode", "write"] as const;
export type Stage = (typeof STAGES)[number];

const LABEL: Record<Stage, string> = {
  detect: "Detect",
  ocr: "OCR",
  translate: "Translate",
  inpaint: "Inpaint",
  render: "Render",
  encode: "Encode",
  write: "Write",
};

/** Index of the stage on the track, or -1 before the first, or 7 after the last. */
export function stageIndex(stage: string | undefined): number {
  if (!stage || stage === "item_start") return -1;
  if (stage === "item_done") return STAGES.length;
  return STAGES.indexOf(stage as Stage);
}

export function ProgressBar({
  value,
  max = 100,
  indeterminate = false,
  label,
  size,
  tone,
  showValue = false,
}: {
  value: number;
  max?: number;
  indeterminate?: boolean;
  /** The accessible name. Required: a bar with no name is a decoration. */
  label: string;
  size?: "sm";
  tone?: "danger";
  showValue?: boolean;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  const done = !indeterminate && pct >= 100;
  const bar = (
    <div
      className={[
        "progress",
        size,
        tone,
        indeterminate ? "indeterminate" : "",
        done ? "done" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={indeterminate ? undefined : value}
      aria-busy={!done}
    >
      <div className="fill" style={indeterminate ? undefined : { width: `${pct}%` }} />
    </div>
  );
  if (!showValue) return bar;
  return (
    <div className="progress-row">
      {bar}
      <span className="value" aria-hidden>
        {Math.round(pct)}%
      </span>
    </div>
  );
}

/** Seven pips and the line between them. `stage` is the one in flight. */
export function StageTrack({ stage }: { stage: string | undefined }) {
  const at = stageIndex(stage);
  return (
    <ol className="stages" aria-label="Pipeline stages">
      {STAGES.map((s, i) => {
        const state = i < at ? "done" : i === at ? "active" : "todo";
        return (
          <li
            key={s}
            className={`stage ${state}`}
            aria-current={state === "active" ? "step" : undefined}
          >
            <span className="pip">{state === "done" && <Icon name="check" size={10} />}</span>
            <span>{LABEL[s]}</span>
          </li>
        );
      })}
    </ol>
  );
}
