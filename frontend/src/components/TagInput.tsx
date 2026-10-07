import { forwardRef, useImperativeHandle, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { Plus, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { mergeTags, normalizeTag, parseTagTokens } from '@/lib/tags';
import { cn } from '@/lib/utils';

export type TagInputHandle = {
  commitDraft: () => string[];
};

export const TagInput = forwardRef<
  TagInputHandle,
  {
    id?: string;
    value: string[];
    onChange: (tags: string[]) => void;
    disabled?: boolean;
    placeholder?: string;
    addLabel: string;
    removeLabel: (tag: string) => string;
    suggestions?: string[];
    describedBy?: string;
  }
>(function TagInput(
  { id, value, onChange, disabled, placeholder, addLabel, removeLabel, suggestions = [], describedBy },
  ref,
) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState('');
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);

  const filtered = useMemo(() => {
    const query = draft.trim().toLowerCase();
    if (!query) return [];
    return suggestions
      .filter((tag) => !value.includes(tag) && tag.toLowerCase().includes(query))
      .slice(0, 8);
  }, [draft, suggestions, value]);

  function apply(next: string[]): string[] {
    const same = next.length === value.length && next.every((tag, index) => tag === value[index]);
    if (!same) onChange(next);
    return next;
  }

  function commit(raw: string): string[] {
    const next = mergeTags(value, parseTagTokens(raw));
    setDraft('');
    setOpen(false);
    setHighlight(-1);
    return apply(next);
  }

  useImperativeHandle(ref, () => ({
    commitDraft: () => commit(draft),
  }));

  function addSuggestion(tag: string) {
    const next = mergeTags(value, [tag]);
    setDraft('');
    setOpen(false);
    setHighlight(-1);
    apply(next);
    inputRef.current?.focus();
  }

  function onDraftChange(raw: string) {
    if (!/[,;]/.test(raw)) {
      setDraft(raw);
      setOpen(true);
      setHighlight(-1);
      return;
    }
    const bits = raw.split(/[,;]/);
    const complete = bits.slice(0, -1).map(normalizeTag).filter(Boolean);
    apply(mergeTags(value, complete));
    setDraft(bits.at(-1) ?? '');
    setOpen(true);
    setHighlight(-1);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.nativeEvent.isComposing || event.key === 'Process') return;
    const mod = event.metaKey || event.ctrlKey;
    if (mod && event.key.toLowerCase() === 's') {
      commit(draft);
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      event.stopPropagation();
      const picked = open && highlight >= 0 ? filtered[highlight] : undefined;
      if (picked) addSuggestion(picked);
      else if (draft.trim()) commit(draft);
      return;
    }
    if (event.key === 'Escape') {
      setOpen(false);
      setHighlight(-1);
      return;
    }
    if (event.key === 'ArrowDown' && filtered.length) {
      event.preventDefault();
      setOpen(true);
      setHighlight((index) => (index + 1) % filtered.length);
      return;
    }
    if (event.key === 'ArrowUp' && filtered.length) {
      event.preventDefault();
      setOpen(true);
      setHighlight((index) => (index <= 0 ? filtered.length - 1 : index - 1));
      return;
    }
    if (event.key === 'Backspace' && draft.length === 0 && value.length > 0) {
      event.preventDefault();
      apply(value.slice(0, -1));
    }
  }

  const listId = id ? `${id}-suggestions` : undefined;
  const showList = open && !disabled && filtered.length > 0;
  const canAdd = Boolean(draft.trim()) && !disabled;

  return (
    <div className="relative">
      <div
        className={cn(
          'flex min-h-9 w-full flex-wrap items-center gap-1 rounded-md border border-input bg-muted/40 px-1.5 py-1 shadow-sm',
          'focus-within:outline-none focus-within:ring-2 focus-within:ring-ring',
          disabled && 'cursor-not-allowed opacity-50',
        )}
        onClick={() => inputRef.current?.focus()}
      >
        {value.map((tag) => (
          <Badge key={tag} variant="secondary" className="h-6 max-w-full gap-0.5 rounded-full pr-0.5">
            <span className="max-w-[10rem] truncate">{tag}</span>
            {disabled ? null : (
              <button
                type="button"
                className="rounded-full p-0.5 hover:bg-background/70 hover:text-destructive"
                aria-label={removeLabel(tag)}
                onClick={(event) => {
                  event.stopPropagation();
                  apply(value.filter((item) => item !== tag));
                }}
              >
                <X className="size-3" />
              </button>
            )}
          </Badge>
        ))}
        <span className="inline-flex min-w-0 flex-1 items-center gap-1">
          <input
            ref={inputRef}
            id={id}
            value={draft}
            disabled={disabled}
            placeholder={value.length ? undefined : placeholder}
            autoComplete="off"
            role="combobox"
            aria-describedby={describedBy}
            aria-autocomplete="list"
            aria-expanded={showList}
            aria-controls={showList ? listId : undefined}
            aria-activedescendant={
              showList && highlight >= 0 && filtered[highlight] ? `${listId}-${highlight}` : undefined
            }
            className="h-6 min-w-[5rem] flex-1 bg-transparent px-1 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={onKeyDown}
            onFocus={() => setOpen(true)}
            onBlur={() => {
              commit(draft);
              setOpen(false);
            }}
          />
          <button
            type="button"
            tabIndex={-1}
            disabled={!canAdd}
            aria-label={addLabel}
            title={addLabel}
            className="inline-flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-background hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
            onMouseDown={(event) => {
              event.preventDefault();
              if (canAdd) commit(draft);
            }}
          >
            <Plus className="size-3.5" />
          </button>
        </span>
      </div>
      {showList ? (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-50 mt-1 max-h-40 w-full overflow-auto rounded-md border bg-popover p-1 text-sm text-popover-foreground shadow-md"
        >
          {filtered.map((tag, index) => (
            <li
              id={`${listId}-${index}`}
              key={tag}
              role="option"
              aria-selected={index === highlight}
              className={cn(
                'cursor-pointer rounded-sm px-2 py-1.5',
                index === highlight && highlight >= 0
                  ? 'bg-accent text-accent-foreground'
                  : 'hover:bg-accent/60',
              )}
              onMouseDown={(event) => {
                event.preventDefault();
                addSuggestion(tag);
              }}
              onMouseEnter={() => setHighlight(index)}
            >
              {tag}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
});

TagInput.displayName = 'TagInput';
