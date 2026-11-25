import { useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { HOVER_CARD } from '@/components/hoverCard';
import { ModelHoverCard } from '@/components/ModelHoverCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { modelLabel, type ModelFacts } from '@/lib/modelName';
import { cn } from '@/lib/utils';

// Hover cards (HOVER_CARD): a card, not the dark one-line tooltip; above the open list (z-[80]).
export function ModelCombobox({
  id,
  value,
  options,
  disabled,
  onChange,
  placeholder,
  noModelsLabel,
  customValueLabel,
  emptyLabel,
  restrictToOptions,
  facts,
  blocked,
}: {
  id?: string;
  value: string;
  options: string[];
  disabled?: boolean;
  onChange: (value: string) => void;
  placeholder?: string;
  noModelsLabel?: string;
  customValueLabel?: (name: string) => string;
  emptyLabel?: string;
  restrictToOptions?: boolean;
  /** Parameters, quantization and size per model name, for the hover card. */
  facts?: ReadonlyMap<string, ModelFacts>;
  /** Why a model cannot be picked; such entries stay visible but greyed out. */
  blocked?: (name: string) => string | null;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  // The card on the closed field; never while the list is open, and not when the list
  // hands focus back to the field after a pick (focus opens a tooltip too).
  const [hint, setHint] = useState(false);
  const closedAt = useRef(0);

  const names =
    restrictToOptions || !value || options.includes(value) ? options : [value, ...options];
  const query = search.trim().toLowerCase();
  const filtered = query
    ? names.filter((item) => {
        const label = modelLabel(item);
        return [item, label.name, label.publisher ?? ''].some((part) => part.toLowerCase().includes(query));
      })
    : names;
  const exact = names.some((item) => item.toLowerCase() === query);

  function commit(next: string) {
    if (restrictToOptions && next && !options.includes(next)) return;
    if (next && blocked?.(next)) return;
    onChange(next);
    closedAt.current = Date.now();
    setOpen(false);
    setSearch('');
  }

  const shown = value ? modelLabel(value) : null;

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        if (!next) closedAt.current = Date.now();
        setOpen(next);
        if (next) setSearch('');
      }}
    >
      <Tooltip
        open={hint && !open && Boolean(value)}
        onOpenChange={(next) => setHint(next && Date.now() - closedAt.current > 400)}
      >
        <TooltipTrigger asChild>
          <PopoverTrigger asChild>
            <Button
              id={id}
              type="button"
              variant="outline"
              role="combobox"
              aria-expanded={open}
              disabled={disabled}
              className="h-8 w-full min-w-0 max-w-full justify-between overflow-hidden px-2.5 text-left font-normal"
            >
              <span className={cn('min-w-0 flex-1 truncate text-left', !value && 'text-muted-foreground')}>
                {shown?.name || placeholder}
              </span>
              <ChevronDown className="size-4 shrink-0 opacity-60" />
            </Button>
          </PopoverTrigger>
        </TooltipTrigger>
        {value ? (
          <TooltipContent side="left" align="start" className={HOVER_CARD}>
            <ModelHoverCard name={value} facts={facts?.get(value)} />
          </TooltipContent>
        ) : null}
      </Tooltip>
      <PopoverContent align="start" sideOffset={4} className="z-[80] w-[var(--radix-popover-trigger-width)] p-1">
        <Input
          value={search}
          autoFocus
          disabled={disabled}
          placeholder={placeholder}
          className="mb-1 h-8"
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            const next = search.trim();
            if (!next) return;
            if (exact) {
              const match = names.find((item) => item.toLowerCase() === query);
              if (match) commit(match);
              return;
            }
            if (restrictToOptions) {
              if (filtered.length === 1) commit(filtered[0]);
              return;
            }
            commit(next);
          }}
        />
        <ul className="max-h-48 overflow-auto">
          {emptyLabel && !query ? (
            <li>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm text-muted-foreground hover:bg-accent"
                onClick={() => commit('')}
              >
                {emptyLabel}
              </button>
            </li>
          ) : null}
          {filtered.map((item) => (
            <li key={item}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    aria-disabled={Boolean(blocked?.(item))}
                    className={cn(
                      'flex w-full min-w-0 items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm',
                      blocked?.(item) ? 'cursor-not-allowed text-muted-foreground opacity-60' : 'hover:bg-accent',
                    )}
                    onClick={() => commit(item)}
                  >
                    <Check className={cn('size-3.5 shrink-0', item === value ? 'opacity-100' : 'opacity-0')} />
                    <span className="min-w-0 flex-1 truncate">{modelLabel(item).name}</span>
                    {blocked?.(item) ? <span className="shrink-0 text-[11px]">{blocked(item)}</span> : null}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="left" align="start" className={HOVER_CARD}>
                  <ModelHoverCard name={item} facts={facts?.get(item)} />
                </TooltipContent>
              </Tooltip>
            </li>
          ))}
          {query && !exact && !restrictToOptions && customValueLabel ? (
            <li>
              <button
                type="button"
                className="flex w-full rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
                onClick={() => commit(search.trim())}
              >
                {customValueLabel(search.trim())}
              </button>
            </li>
          ) : null}
          {filtered.length === 0 && !query ? (
            <li className="px-2 py-1.5 text-sm text-muted-foreground">{noModelsLabel}</li>
          ) : null}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
