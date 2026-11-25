// A date field that always reads and shows MM/DD/YYYY, whatever the browser's language.
// The value in and out is ISO (YYYY-MM-DD), so it is a drop-in for <input type="date">:
// existing handlers keep using `e.target.value`.
import { useEffect, useRef, useState, type ReactElement } from 'react';
import { fmtDate, maskDate, parseDate } from '../dates';

export interface DateInputProps {
  value: string | null | undefined;
  onChange: (e: { target: { value: string } }) => void;
  id?: string;
  className?: string;
  required?: boolean;
  disabled?: boolean;
  title?: string;
  'aria-label'?: string;
  /** ISO bounds, used by the calendar button. */
  min?: string;
  max?: string;
}

export default function DateInput({ value, onChange, className = 'input', min, max, ...rest }: DateInputProps): ReactElement {
  const shown = fmtDate(value);
  const [text, setText] = useState(shown);
  const [bad, setBad] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  // Follow the value when it changes from outside (opening the form, picking in the calendar).
  useEffect(() => { setText(shown); setBad(false); }, [shown]);

  function typed(raw: string) {
    // Deleting is allowed to pass through untouched so the cursor is not fought.
    const next = raw.length < text.length ? raw : maskDate(raw);
    setText(next);
    if (next === '') { setBad(false); onChange({ target: { value: '' } }); return; }
    const iso = parseDate(next);
    setBad(next.length === 10 && iso === null);
    if (iso) onChange({ target: { value: iso } });
  }

  return (
    <div className="relative">
      <input
        {...rest}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        placeholder="MM/DD/YYYY"
        maxLength={10}
        className={`${className} pr-10 ${bad ? 'border-flamingo' : ''}`}
        aria-invalid={bad || undefined}
        value={text}
        onChange={(e) => typed(e.target.value)}
        onBlur={() => { if (parseDate(text) === null) { setText(shown); setBad(false); } }}
      />
      <button
        type="button"
        tabIndex={-1}
        aria-label="Open calendar"
        title="Pick from calendar"
        disabled={rest.disabled}
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-1 text-grape-soft hover:text-white"
        onClick={() => { try { picker.current?.showPicker(); } catch { picker.current?.focus(); } }}
      >
        📅
      </button>
      {/* The browser's own calendar, used only as a picker: it is hidden and never typed in. */}
      <input
        ref={picker}
        type="date"
        tabIndex={-1}
        aria-hidden="true"
        min={min}
        max={max}
        value={value ?? ''}
        onChange={(e) => onChange({ target: { value: e.target.value } })}
        className="pointer-events-none absolute bottom-0 right-0 h-0 w-0 opacity-0"
      />
    </div>
  );
}
