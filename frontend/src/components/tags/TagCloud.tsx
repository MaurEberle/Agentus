import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import { compatibleTags, type TagMatch } from '@/lib/tags';
import { cn } from '@/lib/utils';

/** Inner width that wraps the chips into a roughly square cloud, including the mode row. */
function squareCloudWidth(tags: string[]): number {
  const chip = (tag: string) => Math.ceil(tag.length * 6.6 + 22);
  const widths = tags.map(chip);
  const longest = Math.max(0, ...widths);
  const total = widths.reduce((sum, width) => sum + width, 0) + 6 * Math.max(0, tags.length - 1);
  const modeRow = 32;
  const row = 28;
  const side = (modeRow + Math.sqrt(modeRow * modeRow + 4 * total * row)) / 2;
  return Math.ceil(Math.max(side, longest, 168));
}

export function TagCloudPanel({
  tags,
  tagSets,
  selected,
  mode,
  onToggle,
  onModeChange,
  label,
  className,
}: {
  tags: string[];
  tagSets: readonly (readonly string[])[];
  selected: string[];
  mode: TagMatch;
  onToggle: (tag: string) => void;
  onModeChange: (mode: TagMatch) => void;
  label: string;
  className?: string;
}) {
  const { t } = useTranslation();
  const allowed = compatibleTags(tagSets, selected, mode);
  return (
    <div className={cn('flex min-w-0 flex-col', className)}>
      <div className="flex items-center justify-end gap-2">
        <span className={cn('text-xs', mode === 'and' ? 'font-medium text-foreground' : 'text-muted-foreground')}>
          {t('tagCloud.and')}
        </span>
        <Switch
          checked={mode === 'or'}
          onCheckedChange={(value) => onModeChange(value ? 'or' : 'and')}
          aria-label={t('tagCloud.mode')}
          className="h-6 w-11 border-border bg-background p-0.5 data-[state=checked]:bg-background data-[state=unchecked]:bg-background [&>span]:bg-primary [&>span]:data-[state=checked]:translate-x-5"
        />
        <span className={cn('text-xs', mode === 'or' ? 'font-medium text-foreground' : 'text-muted-foreground')}>
          {t('tagCloud.or')}
        </span>
      </div>
      {tags.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">{t('tagCloud.empty')}</p>
      ) : (
        <div className="mt-2 flex min-w-0 flex-wrap justify-start gap-1.5 overflow-auto" role="group" aria-label={label}>
          {tags.map((tag) => {
            const on = selected.includes(tag);
            const blocked = allowed !== null && !allowed.has(tag);
            return (
              <button
                key={tag}
                type="button"
                aria-pressed={on}
                disabled={blocked}
                onClick={() => onToggle(tag)}
                className={cn(
                  'rounded-full border px-2.5 py-0.5 text-xs font-medium',
                  on
                    ? 'border-transparent bg-primary text-primary-foreground'
                    : 'border-border text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                  blocked && 'cursor-not-allowed opacity-40 hover:bg-transparent hover:text-muted-foreground',
                )}
              >
                {tag}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function TagCloud({
  tags,
  tagSets,
  selected,
  mode,
  onToggle,
  onClear,
  onModeChange,
  label,
}: {
  tags: string[];
  tagSets: readonly (readonly string[])[];
  selected: string[];
  mode: TagMatch;
  onToggle: (tag: string) => void;
  onClear: () => void;
  onModeChange: (mode: TagMatch) => void;
  label: string;
}) {
  const { t } = useTranslation();
  return (
    <Popover>
      <div className="inline-flex">
        <PopoverTrigger asChild>
          <Button type="button" size="sm" variant="outline" className={selected.length ? 'rounded-r-none' : undefined}>
            {label}
            {selected.length ? ` (${selected.length})` : ''}
          </Button>
        </PopoverTrigger>
        {selected.length > 0 ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="rounded-l-none border-l-0 px-1.5"
            aria-label={t('tagCloud.clear')}
            onClick={onClear}
          >
            <X className="size-3.5" />
          </Button>
        ) : null}
      </div>
      <PopoverContent
        align="start"
        style={tags.length ? { width: `min(50vw, ${squareCloudWidth(tags) + 24}px)` } : undefined}
        className="flex max-h-[50vh] max-w-[50vw] flex-col overflow-auto p-3"
      >
        <TagCloudPanel
          tags={tags}
          tagSets={tagSets}
          selected={selected}
          mode={mode}
          onToggle={onToggle}
          onModeChange={onModeChange}
          label={label}
        />
      </PopoverContent>
    </Popover>
  );
}
