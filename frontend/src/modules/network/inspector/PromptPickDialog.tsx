import { useEffect, useMemo, useState } from 'react';
import { ArrowUpDown } from 'lucide-react';
import { WidthGrip } from '@/modules/monitoring/PaneGrips';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { TagCloudPanel } from '@/components/tags/TagCloud';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { notify } from '@/lib/notifications';
import { matchesTags, type TagMatch } from '@/lib/tags';
import { cn } from '@/lib/utils';
import { getPrompt, listPrompts } from '@/modules/prompts/api';
import type { PromptListItem } from '@/modules/prompts/model';

function clampShare(value: number): number {
  if (!Number.isFinite(value)) return 0.55;
  return Math.min(0.75, Math.max(0.35, value));
}

export function PromptPickDialog({
  open,
  onOpenChange,
  onPick,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (prompt: { name: string; body: string }) => void;
}) {
  const { t } = useTranslation();
  const { data } = useQuery({ queryKey: ['prompts'], queryFn: listPrompts, enabled: open });
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'name' | 'updatedAt'>('updatedAt');
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const [tagMode, setTagMode] = useState<TagMatch>('or');
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listShare, setListShare] = useState(0.55);
  const library = data?.items ?? [];
  const tagSets = library.map((item) => item.tags);
  const cloudTags = useMemo(() => {
    const tags = new Set<string>();
    for (const item of library) for (const tag of item.tags) tags.add(tag);
    return [...tags].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
  }, [library]);

  useEffect(() => {
    if (open) return;
    setQuery('');
    setTagFilter([]);
    setTagMode('or');
    setSelected(null);
    setBusy(false);
  }, [open]);

  const items = useMemo(() => {
    const list = [...library];
    const needle = query.trim().toLowerCase();
    const filtered = list.filter((item) => {
      if (!matchesTags(item.tags, tagFilter, tagMode)) return false;
      if (!needle) return true;
      return `${item.name} ${item.description} ${item.tags.join(' ')}`.toLowerCase().includes(needle);
    });
    filtered.sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
      return b.updatedAt.localeCompare(a.updatedAt);
    });
    return filtered;
  }, [library, query, sort, tagFilter, tagMode]);

  const tagSelectionKey = `${tagMode}\n${tagFilter.join('\n')}`;
  useEffect(() => {
    setSelected((current) => (current && items.some((item) => item.id === current) ? current : null));
  }, [tagSelectionKey]);

  async function apply() {
    if (!selected || busy) return;
    setBusy(true);
    try {
      const detail = await getPrompt(selected);
      onPick({ name: detail.name, body: detail.body });
      onOpenChange(false);
    } catch {
      notify({ titleKey: 'network.inspector.prompt.failed', variant: 'error' });
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={t('network.dialog.close')} className="w-full max-w-4xl">
        <DialogHeader>
          <DialogTitle>{t('network.inspector.prompt.title')}</DialogTitle>
          <DialogDescription>{t('network.inspector.prompt.body')}</DialogDescription>
        </DialogHeader>
        <div data-split-row className="flex h-80 w-full min-w-0">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
            <div className="flex items-center gap-2">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t('network.inspector.prompt.search')}
                aria-label={t('network.inspector.prompt.search')}
                className="h-8 min-w-0 flex-1"
              />
              <Select value={sort} onValueChange={(value) => setSort(value as typeof sort)}>
                <SelectTrigger
                  className="w-40 shrink-0"
                  aria-label={`${t('network.inspector.prompt.sort')}: ${t(sort === 'name' ? 'network.inspector.prompt.sortName' : 'network.inspector.prompt.sortUpdated')}`}
                >
                  <ArrowUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="updatedAt">{t('network.inspector.prompt.sortUpdated')}</SelectItem>
                  <SelectItem value="name">{t('network.inspector.prompt.sortName')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <ScrollArea className="min-h-0 flex-1">
              {items.length === 0 ? (
                <p className="px-1 text-sm text-muted-foreground">
                  {t(library.length ? 'network.inspector.prompt.filter' : 'network.inspector.prompt.empty')}
                </p>
              ) : (
                <ul className="space-y-1 pr-3">
                  {items.map((item) => (
                    <PromptRow key={item.id} item={item} selected={selected === item.id} onSelect={() => setSelected(item.id)} />
                  ))}
                </ul>
              )}
            </ScrollArea>
          </div>
          <WidthGrip
            label={t('network.inspector.prompt.split')}
            share={listShare}
            onChange={(next) => setListShare(clampShare(next))}
          />
          <div className="flex h-full min-h-0 min-w-0 shrink-0 flex-col" style={{ width: `${(1 - listShare) * 100}%` }}>
            <TagCloudPanel
              tags={cloudTags}
              tagSets={tagSets}
              selected={tagFilter}
              mode={tagMode}
              onToggle={(tag) => setTagFilter((current) => (current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag]))}
              onModeChange={setTagMode}
              label={t('prompts.filter.tags')}
              className="h-full min-h-0 w-full"
            />
          </div>
        </div>
        <DialogFooter className="sm:justify-between">
          <Button asChild variant="link" size="sm">
            <Link to="/prompts">{t('network.inspector.prompt.library')}</Link>
          </Button>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('network.dialog.cancel')}
            </Button>
            <Button type="button" disabled={!selected || busy} onClick={() => void apply()}>
              {t('network.inspector.prompt.apply')}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PromptRow({ item, selected, onSelect }: { item: PromptListItem; selected: boolean; onSelect: () => void }) {
  const button = (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'flex h-9 w-full items-center rounded-md border px-3 text-left text-xs font-medium',
        selected ? 'border-primary bg-accent' : 'hover:bg-accent',
      )}
    >
      <span className="truncate">{item.name}</span>
    </button>
  );
  if (!item.description) return <li>{button}</li>;
  return (
    <li>
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent className="max-w-xs">{item.description}</TooltipContent>
      </Tooltip>
    </li>
  );
}
