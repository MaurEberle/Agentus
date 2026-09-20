import { useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

export function ModelCombobox({
  id,
  value,
  options,
  disabled,
  onChange,
  placeholder,
  noModelsLabel,
  useValueLabel,
  emptyLabel,
}: {
  id?: string;
  value: string;
  options: string[];
  disabled?: boolean;
  onChange: (value: string) => void;
  placeholder?: string;
  noModelsLabel?: string;
  useValueLabel?: (name: string) => string;
  emptyLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const names = value && !options.includes(value) ? [value, ...options] : options;
  const query = search.trim().toLowerCase();
  const filtered = query ? names.filter((item) => item.toLowerCase().includes(query)) : names;
  const exact = names.some((item) => item.toLowerCase() === query);

  function commit(next: string) {
    onChange(next);
    setOpen(false);
    setSearch('');
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setSearch('');
      }}
    >
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          title={value || undefined}
          className="h-8 w-full min-w-0 max-w-full justify-between overflow-hidden px-2.5 text-left font-normal"
        >
          <span className={cn('min-w-0 flex-1 truncate text-left', !value && 'text-muted-foreground')}>
            {value || placeholder}
          </span>
          <ChevronDown className="size-4 shrink-0 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" sideOffset={4} className="z-[80] w-[var(--radix-popover-trigger-width)] p-1">
        <Input
          value={search}
          autoFocus
          disabled={disabled}
          placeholder={placeholder}
          className="mb-1 h-8"
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              const next = search.trim();
              if (next) commit(next);
            }
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
              <button
                type="button"
                className="flex w-full min-w-0 items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
                title={item}
                onClick={() => commit(item)}
              >
                <Check className={cn('size-3.5 shrink-0', item === value ? 'opacity-100' : 'opacity-0')} />
                <span className="min-w-0 flex-1 truncate">{item}</span>
              </button>
            </li>
          ))}
          {query && !exact && useValueLabel ? (
            <li>
              <button
                type="button"
                className="flex w-full rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
                onClick={() => commit(search.trim())}
              >
                {useValueLabel(search.trim())}
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
