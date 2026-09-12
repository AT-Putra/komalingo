/**
 * A path input with a Browse button.
 *
 * The native dialog fills the field; typing still works, because a picker
 * that cannot reach a network share or a path the user has on the clipboard
 * is a picker the user routes around. The field is the source of truth and
 * the dialog is one way to write it.
 */

import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { Icon } from "./Icon";

export function PathField({
  id,
  label,
  hint,
  value,
  onChange,
  mode,
  filters,
  placeholder,
  disabled,
}: {
  id: string;
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  mode: "file" | "directory";
  filters?: { name: string; extensions: string[] }[];
  placeholder?: string;
  disabled?: boolean;
}) {
  const [note, setNote] = useState("");

  async function browse() {
    setNote("");
    try {
      const picked = await open({
        title: label,
        directory: mode === "directory",
        multiple: false,
        filters,
        defaultPath: value || undefined,
      });
      if (typeof picked === "string") onChange(picked);
    } catch (e) {
      setNote(String(e));
    }
  }

  return (
    <div className="field">
      <label className="label" htmlFor={id}>
        {label}
      </label>
      <div className="control">
        <input
          id={id}
          className="input-path"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          spellCheck={false}
          autoComplete="off"
          disabled={disabled}
          aria-describedby={hint ? `${id}-hint` : undefined}
        />
        <button type="button" className="btn" onClick={browse} disabled={disabled}>
          <Icon name={mode === "directory" ? "folder-open" : "file"} />
          Browse
        </button>
      </div>
      {(hint || note) && (
        <span id={`${id}-hint`} className="hint">
          {note || hint}
        </span>
      )}
    </div>
  );
}
