import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
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
import { notify } from '@/lib/notifications';
import { formatRelative } from '@/lib/relativeTime';
import { getPrompt, listPrompts } from '@/modules/prompts/api';
import type { PromptListItem } from '@/modules/prompts/model';

export function PromptPickDialog({
  open,
  onOpenChange,
  onPick,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (body: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const { data } = useQuery({ queryKey: ['prompts'], queryFn: listPrompts, enabled: open });
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'name' | 'updatedAt'>('updatedAt');
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) return;
    setQuery('');
    setSelected(null);
    setBusy(false);
  }, [open]);

  const items = useMemo(() => {
    const list = [...(data?.items ?? [])];
    const needle = query.trim().toLowerCase();
    const filtered = needle
      ? list.filter((item) => `${item.name} ${item.description} ${item.tags.join(' ')}`.toLowerCase().includes(needle))
      : list;
    filtered.sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
      return b.updatedAt.localeCompare(a.updatedAt);
    });
    return filtered;
  }, [data?.items, query, sort]);

  async function apply() {
    if (!selected || busy) return;
    setBusy(true);
    try {
      const detail = await getPrompt(selected);
      onPick(detail.body);
      onOpenChange(false);
    } catch {
      notify({ titleKey: 'network.inspector.prompt.failed', variant: 'error' });
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={t('network.dialog.close')} className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('network.inspector.prompt.title')}</DialogTitle>
          <DialogDescription>{t('network.inspector.prompt.body')}</DialogDescription>
        </DialogHeader>
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('network.inspector.prompt.search')}
          />
          <Select value={sort} onValueChange={(value) => setSort(value as typeof sort)}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="updatedAt">{t('network.inspector.prompt.sortUpdated')}</SelectItem>
              <SelectItem value="name">{t('network.inspector.prompt.sortName')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <ScrollArea className="h-64">
          {items.length === 0 ? (
            <p className="px-1 text-sm text-muted-foreground">
              {t(data?.items.length ? 'network.inspector.prompt.filter' : 'network.inspector.prompt.empty')}
            </p>
          ) : (
            <ul className="space-y-1 pr-2">
              {items.map((item) => (
                <PromptRow
                  key={item.id}
                  item={item}
                  selected={selected === item.id}
                  locale={i18n.language}
                  onSelect={() => setSelected(item.id)}
                />
              ))}
            </ul>
          )}
        </ScrollArea>
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

function PromptRow({
  item,
  selected,
  locale,
  onSelect,
}: {
  item: PromptListItem;
  selected: boolean;
  locale: string;
  onSelect: () => void;
}) {
  const tags = item.tags.slice(0, 3);
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className={`flex w-full flex-col gap-1 rounded-md border px-3 py-2 text-left text-sm ${selected ? 'border-primary bg-accent' : 'hover:bg-accent'}`}
      >
        <span className="flex items-center justify-between gap-2">
          <span className="min-w-0 truncate font-medium">{item.name}</span>
          {tags.length > 0 ? (
            <span className="flex shrink-0 gap-1">
              {tags.map((tag) => (
                <Badge key={tag} variant="outline">
                  {tag}
                </Badge>
              ))}
            </span>
          ) : null}
        </span>
        <span className="truncate text-xs text-muted-foreground">
          {item.description || '—'}
          {' · '}
          {formatRelative(Date.parse(item.updatedAt), locale)}
        </span>
      </button>
    </li>
  );
}
