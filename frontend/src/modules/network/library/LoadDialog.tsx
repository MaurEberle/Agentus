import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
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
import { formatRelative } from '@/lib/relativeTime';
import type { NetworkListItem } from '@/modules/dashboard/model';
import { useEditorNetworksQuery } from '@/modules/network/api';

export function LoadDialog({
  open,
  onOpenChange,
  onOpen,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onOpen: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const { data } = useEditorNetworksQuery();
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'name' | 'updatedAt' | 'lastUsedAt'>('updatedAt');
  const [selected, setSelected] = useState<string | null>(null);

  const items = useMemo(() => {
    const list = [...(data?.items ?? [])];
    const q = query.trim().toLowerCase();
    const filtered = q
      ? list.filter((item) => `${item.name} ${item.description ?? ''}`.toLowerCase().includes(q))
      : list;
    filtered.sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name);
      const av = Date.parse(sort === 'lastUsedAt' ? (a.lastUsedAt ?? a.updatedAt) : a.updatedAt);
      const bv = Date.parse(sort === 'lastUsedAt' ? (b.lastUsedAt ?? b.updatedAt) : b.updatedAt);
      return bv - av;
    });
    return filtered;
  }, [data?.items, query, sort]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={t('network.dialog.close')} className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('network.load.title')}</DialogTitle>
          <DialogDescription>{t('network.load.body')}</DialogDescription>
        </DialogHeader>
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('network.load.search')}
          />
          <Select value={sort} onValueChange={(value) => setSort(value as typeof sort)}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="updatedAt">{t('network.load.sortUpdated')}</SelectItem>
              <SelectItem value="name">{t('network.load.sortName')}</SelectItem>
              <SelectItem value="lastUsedAt">{t('network.load.sortUsed')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <ScrollArea className="h-64">
          <ul className="space-y-1 pr-2">
            {items.map((item) => (
              <LoadRow
                key={item.id}
                item={item}
                selected={selected === item.id}
                locale={i18n.language}
                onSelect={() => setSelected(item.id)}
              />
            ))}
          </ul>
        </ScrollArea>
        <DialogFooter className="sm:justify-between">
          <Button asChild variant="link" size="sm">
            <Link to="/networks">{t('network.ribbon.library')}</Link>
          </Button>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('network.dialog.cancel')}
            </Button>
            <Button type="button" disabled={!selected} onClick={() => selected && onOpen(selected)}>
              {t('network.load.open')}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function LoadRow({
  item,
  selected,
  locale,
  onSelect,
}: {
  item: NetworkListItem;
  selected: boolean;
  locale: string;
  onSelect: () => void;
}) {
  const { t } = useTranslation();
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className={`flex w-full flex-col gap-1 rounded-md border px-3 py-2 text-left text-sm ${selected ? 'border-primary bg-accent' : 'hover:bg-accent'}`}
      >
        <span className="flex items-center justify-between gap-2">
          <span className="font-medium">{item.name}</span>
          <span className="flex gap-1">
            <Badge variant={item.validationStatus === 'valid' ? 'default' : 'destructive'}>
              {t(`network.badge.${item.validationStatus === 'valid' ? 'valid' : 'invalid'}`)}
            </Badge>
            {item.isActive ? <Badge>{t('network.badge.active')}</Badge> : null}
            {item.isRunning ? <Badge variant="warning">{t('network.badge.running')}</Badge> : null}
          </span>
        </span>
        <span className="text-xs text-muted-foreground">
          {t('network.load.preview', { nodes: item.nodeCount, edges: item.edgeCount })}
          {' · '}
          {formatRelative(Date.parse(item.updatedAt), locale)}
        </span>
      </button>
    </li>
  );
}
