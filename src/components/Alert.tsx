/**
 * One box per message, with an icon that says the same thing the colour does.
 *
 * `error` renders its children inside a <pre>: the provider's own status and
 * body arrive here verbatim (AC-8) and their line breaks are part of the
 * message. The other tones are prose.
 */

import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

type Tone = "error" | "warn" | "info" | "success";

const ICON: Record<Tone, IconName> = {
  error: "alert-circle",
  warn: "alert-triangle",
  info: "info",
  success: "check-circle",
};

export function Alert({
  tone,
  title,
  children,
}: {
  tone: Tone;
  title?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={`alert ${tone}`}
      role={tone === "error" ? "alert" : "status"}
      aria-live={tone === "error" ? "assertive" : "polite"}
    >
      <Icon name={ICON[tone]} />
      <div className="body">
        {title && <div className="title">{title}</div>}
        {tone === "error" ? <pre>{children}</pre> : children}
      </div>
    </div>
  );
}
