/**
 * A searchable combobox for the model id.
 *
 * Typing always works, and the list is optional: the ids come from the user's
 * own endpoint, and an endpoint that refuses to enumerate must not make a
 * model unreachable. So the input is the source of truth and the list is one
 * way to fill it -- the same contract PathField keeps with its Browse button.
 *
 * WAI-ARIA 1.2 combobox with a listbox popup: the input owns focus and points
 * at the active option with aria-activedescendant, so a screen reader hears
 * the option without focus ever leaving the text. Arrow keys move, Enter
 * picks, Escape closes, Tab leaves with whatever is typed.
 *
 * Filtering is by what the user TYPES, not by the field's value. A field
 * holding a full id would otherwise filter the list down to that one row the
 * moment it opened, and forty models would look like one.
 */

import {
  forwardRef,
  useEffect,
  useId,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { Icon } from "./Icon";
import type { ModelInfo } from "../lib/api";

/** Case-insensitive substring match on the id or its owner; "" keeps all. */
function filter(options: ModelInfo[], q: string): ModelInfo[] {
  if (!q) return options;
  return options.filter(
    (m) => m.id.toLowerCase().includes(q) || (m.owned_by ?? "").toLowerCase().includes(q),
  );
}

export interface ModelComboboxHandle {
  /** Focus the input and open the list -- what Load models does on success. */
  open(): void;
}

export const ModelCombobox = forwardRef<
  ModelComboboxHandle,
  {
    id: string;
    value: string;
    onChange: (v: string) => void;
    options: ModelInfo[];
    placeholder?: string;
    disabled?: boolean;
    /** Ids of the element(s) describing the field, for aria-describedby. */
    describedBy?: string;
  }
>(function ModelCombobox({ id, value, onChange, options, placeholder, disabled, describedBy }, ref) {
  const [open, setOpen] = useState(false);
  // The typed filter. "" shows everything, and it is reset whenever the list
  // is opened by a click or an arrow rather than by typing.
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const listId = `${useId()}-list`;

  const q = query.trim().toLowerCase();
  const shown = filter(options, q);

  useImperativeHandle(ref, () => ({
    open() {
      inputRef.current?.focus();
      show();
    },
  }));

  function show() {
    setQuery("");
    setActive(Math.max(0, options.findIndex((m) => m.id === value)));
    setOpen(true);
  }

  function close() {
    setOpen(false);
    setActive(-1);
  }

  function pick(m: ModelInfo) {
    onChange(m.id);
    close();
    inputRef.current?.focus();
  }

  // The list may be re-filtered under the active row; keep it in range.
  useEffect(() => {
    if (active >= shown.length) setActive(shown.length - 1);
  }, [active, shown.length]);

  // Keep the keyboard's row on screen. `nearest`, so a row already visible
  // does not yank the list around.
  useLayoutEffect(() => {
    if (!open || active < 0) return;
    listRef.current?.children[active]?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        if (!open) show();
        else if (shown.length) setActive((i) => (i + 1) % shown.length);
        break;
      case "ArrowUp":
        e.preventDefault();
        if (!open) show();
        else if (shown.length) setActive((i) => (i <= 0 ? shown.length - 1 : i - 1));
        break;
      case "Home":
        if (open && shown.length) {
          e.preventDefault();
          setActive(0);
        }
        break;
      case "End":
        if (open && shown.length) {
          e.preventDefault();
          setActive(shown.length - 1);
        }
        break;
      case "Enter":
        if (open) {
          e.preventDefault();
          if (active >= 0 && active < shown.length) pick(shown[active]);
          else close(); // nothing highlighted: keep what was typed
        }
        break;
      case "Escape":
        if (open) {
          e.preventDefault();
          close();
        }
        break;
      case "Tab":
        close();
        break;
    }
  }

  const activeId = open && active >= 0 && active < shown.length ? `${listId}-${active}` : undefined;

  return (
    <div
      className="combobox"
      onBlur={(e) => {
        // Leaving the whole widget closes it; moving between the input and
        // the toggle does not.
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) close();
      }}
    >
      <input
        ref={inputRef}
        id={id}
        className="input-path"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        aria-describedby={describedBy}
        value={value}
        onChange={(e) => {
          const v = e.target.value;
          onChange(v);
          setQuery(v);
          // Highlight only an EXACT match while typing. Pre-selecting the
          // first partial match would let Enter turn a deliberately typed
          // "gpt-4o" into "gpt-4o-mini"; the list is a suggestion, and the
          // arrow keys are how the user takes one.
          setActive(filter(options, v.trim().toLowerCase()).findIndex((m) => m.id === v.trim()));
          if (!open) setOpen(true);
        }}
        onKeyDown={onKeyDown}
        onClick={() => !open && show()}
        placeholder={placeholder}
        spellCheck={false}
        autoComplete="off"
        disabled={disabled}
      />
      <button
        type="button"
        className="combobox-toggle"
        tabIndex={-1}
        aria-label={open ? "Hide models" : "Show models"}
        aria-expanded={open}
        aria-controls={listId}
        disabled={disabled}
        // mousedown, not click: click would land after the input blurred and
        // the list had already closed on that blur.
        onMouseDown={(e) => {
          e.preventDefault();
          inputRef.current?.focus();
          open ? close() : show();
        }}
      >
        <Icon name={open ? "chevron-up" : "chevron-down"} size={16} />
      </button>

      {open && (
        <div className="combobox-pop">
          {options.length === 0 ? (
            <p className="combobox-empty">
              No list yet. <b>Load models</b> asks the endpoint what it serves; typing an id
              works without it.
            </p>
          ) : shown.length === 0 ? (
            <p className="combobox-empty">
              No model matches <span className="mono">{query.trim()}</span>. Enter keeps it as
              typed.
            </p>
          ) : (
            <ul
              ref={listRef}
              id={listId}
              role="listbox"
              aria-label="Models"
              className="combobox-list"
              // Keep focus in the input while the pointer is on the list.
              onMouseDown={(e) => e.preventDefault()}
            >
              {shown.map((m, i) => {
                const selected = m.id === value;
                return (
                  <li
                    key={m.id}
                    id={`${listId}-${i}`}
                    role="option"
                    aria-selected={selected}
                    className={`combobox-opt${i === active ? " active" : ""}`}
                    onPointerMove={() => i !== active && setActive(i)}
                    onClick={() => pick(m)}
                  >
                    <span className="combobox-check">
                      {selected && <Icon name="check" size={14} />}
                    </span>
                    <span className="combobox-id">{m.id}</span>
                    {m.owned_by && <span className="combobox-owner">{m.owned_by}</span>}
                  </li>
                );
              })}
            </ul>
          )}
          {options.length > 0 && (
            <div className="combobox-count" aria-live="polite">
              {q ? `${shown.length} of ${options.length} models` : `${options.length} models`}
            </div>
          )}
        </div>
      )}
    </div>
  );
});
