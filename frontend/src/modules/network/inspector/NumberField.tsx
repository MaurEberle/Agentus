import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import type { NumberRange } from '@/modules/network/model/ranges';

function parse(text: string): number | null {
  const trimmed = text.trim().replace(',', '.');
  if (!trimmed) return null;
  const value = Number(trimmed);
  return Number.isFinite(value) ? value : null;
}

function valid(value: number, range: NumberRange): boolean {
  if (range.integer && !Number.isInteger(value)) return false;
  return value >= range.min && value <= range.max;
}

function clamp(value: number, range: NumberRange): number {
  const rounded = range.integer ? Math.round(value) : value;
  return Math.min(range.max, Math.max(range.min, rounded));
}

function shown(value: number | undefined): string {
  return value === undefined ? '' : String(value);
}

/**
 * A number setting with a range. A valid value is saved while typing; anything else
 * waits until the field is left and is then clamped into the range (or reset when it
 * is no number). Typing "200" into a field that starts at 10 therefore works.
 */
export function NumberField({
  value,
  onChange,
  range,
  step,
  placeholder,
  readOnly,
  id,
  className,
}: {
  value: number | undefined;
  onChange: (value: number | undefined) => void;
  range: NumberRange;
  step?: number;
  placeholder?: string;
  readOnly?: boolean;
  id?: string;
  className?: string;
}) {
  const { t, i18n } = useTranslation();
  const hintId = useId();
  const [draft, setDraft] = useState(shown(value));
  const [seen, setSeen] = useState(value);
  const [focused, setFocused] = useState(false);
  if (!focused && seen !== value) {
    // The stored value changed elsewhere (undo, another node, a clamp): show it.
    setSeen(value);
    setDraft(shown(value));
  }
  const parsed = parse(draft);
  const invalid = draft.trim() !== '' && (parsed === null || !valid(parsed, range));
  const format = (number: number) => new Intl.NumberFormat(i18n.language).format(number);

  function change(text: string) {
    setDraft(text);
    if (text.trim() === '') {
      onChange(undefined);
      return;
    }
    const next = parse(text);
    if (next !== null && valid(next, range)) onChange(next);
  }

  function leave() {
    setFocused(false);
    if (draft.trim() === '') return;
    const next = parse(draft);
    if (next === null) {
      setDraft(shown(value));
      return;
    }
    const fixed = clamp(next, range);
    if (fixed !== value) onChange(fixed);
    setSeen(fixed);
    setDraft(String(fixed));
  }

  return (
    <>
      <Input
        id={id}
        type="number"
        inputMode={range.integer ? 'numeric' : 'decimal'}
        min={range.min}
        max={range.max}
        step={step ?? (range.integer ? 1 : 'any')}
        value={draft}
        placeholder={placeholder}
        disabled={readOnly}
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? hintId : undefined}
        className={cn(invalid && 'border-destructive focus-visible:ring-destructive', className)}
        onFocus={() => setFocused(true)}
        onChange={(event) => change(event.target.value)}
        onBlur={leave}
      />
      {invalid ? (
        <p id={hintId} className="text-xs text-destructive">
          {t(range.integer ? 'network.inspector.rangeInteger' : 'network.inspector.range', {
            min: format(range.min),
            max: format(range.max),
          })}
        </p>
      ) : null}
    </>
  );
}
