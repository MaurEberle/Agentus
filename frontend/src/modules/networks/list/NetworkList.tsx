import type { KeyboardEvent, MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { formatRelative } from '@/lib/relativeTime';
import type { NetworkListItem } from '@/modules/dashboard/model';
import { validationBadgeVariant } from '@/modules/dashboard/model';
import { formatStamp } from '@/modules/networks/model/format';
import { rangeIds } from '@/modules/networks/model/filter';
import { useNetworksUi } from '@/modules/networks/store';
import { cn } from '@/lib/utils';

export function NetworkList({
  items,
  loading,
  onOpen,
}: {
  items: NetworkListItem[];
  loading: boolean;
  onOpen: (id: string) => void;
}) {
  const isDesktop = useMediaQuery('(min-width: 768px)');
  if (loading) {
    return (
      <div className="space-y-2 p-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }
  return isDesktop ? <DesktopTable items={items} onOpen={onOpen} /> : <MobileCards items={items} onOpen={onOpen} />;
}

function useSelection(items: NetworkListItem[]) {
  const selectedIds = useNetworksUi((state) => state.selectedIds);
  const anchorId = useNetworksUi((state) => state.anchorId);
  const select = useNetworksUi((state) => state.select);
  const visibleIds = items.map((item) => item.id);
  const selectedSet = new Set(selectedIds);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedSet.has(id));

  function onRowClick(event: MouseEvent, id: string) {
    if (event.shiftKey) {
      select(rangeIds(visibleIds, anchorId ?? id, id), anchorId ?? id);
      return;
    }
    if (event.metaKey || event.ctrlKey) {
      const next = selectedSet.has(id) ? selectedIds.filter((item) => item !== id) : [...selectedIds, id];
      select(next, id);
      return;
    }
    select([id], id);
  }

  function toggleOne(id: string) {
    const next = selectedSet.has(id) ? selectedIds.filter((item) => item !== id) : [...selectedIds, id];
    select(next, id);
  }

  function toggleAll() {
    if (allVisibleSelected) {
      select(
        selectedIds.filter((id) => !visibleIds.includes(id)),
        null,
      );
      return;
    }
    select([...new Set([...selectedIds, ...visibleIds])], visibleIds[0] ?? null);
  }

  return { selectedSet, allVisibleSelected, onRowClick, toggleOne, toggleAll };
}

function StatusBadges({ item }: { item: NetworkListItem }) {
  const { t } = useTranslation();
  return (
    <span className="flex flex-wrap gap-1">
      <Badge variant={validationBadgeVariant(item.validationStatus)}>
        {t(`networks.badge.${item.validationStatus}`)}
      </Badge>
      {item.credentialMissing ? <Badge variant="destructive">{t('networks.badge.credentialMissing')}</Badge> : null}
      {item.isActive ? <Badge>{t('networks.badge.active')}</Badge> : null}
      {item.isRunning ? <Badge variant="warning">{t('networks.badge.running')}</Badge> : null}
    </span>
  );
}

function DesktopTable({ items, onOpen }: { items: NetworkListItem[]; onOpen: (id: string) => void }) {
  const { t, i18n } = useTranslation();
  const { selectedSet, allVisibleSelected, onRowClick, toggleOne, toggleAll } = useSelection(items);

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Enter') return;
    const only = [...selectedSet];
    if (only.length === 1) onOpen(only[0]);
  }

  return (
    <div tabIndex={0} onKeyDown={onKey} className="min-h-0 flex-1 overflow-auto outline-none">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <Checkbox
                checked={allVisibleSelected}
                onCheckedChange={() => toggleAll()}
                aria-label={t('networks.list.selectAll')}
              />
            </TableHead>
            <TableHead>{t('networks.list.name')}</TableHead>
            <TableHead className="hidden lg:table-cell">{t('networks.list.description')}</TableHead>
            <TableHead>{t('networks.list.status')}</TableHead>
            <TableHead className="hidden md:table-cell">{t('networks.list.graph')}</TableHead>
            <TableHead>{t('networks.list.updated')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow
              key={item.id}
              data-state={selectedSet.has(item.id) ? 'selected' : undefined}
              className="cursor-pointer"
              onClick={(event) => onRowClick(event, item.id)}
              onDoubleClick={() => onOpen(item.id)}
            >
              <TableCell onClick={(event) => event.stopPropagation()}>
                <Checkbox
                  checked={selectedSet.has(item.id)}
                  onCheckedChange={() => toggleOne(item.id)}
                  aria-label={item.name}
                />
              </TableCell>
              <TableCell>
                <div className="flex flex-col gap-1">
                  <span className="font-medium">{item.name}</span>
                  <TagRow tags={item.tags} />
                </div>
              </TableCell>
              <TableCell className="hidden max-w-xs truncate text-muted-foreground lg:table-cell">
                {item.description || '—'}
              </TableCell>
              <TableCell>
                <StatusBadges item={item} />
              </TableCell>
              <TableCell className="hidden text-muted-foreground md:table-cell">
                {t('networks.list.counts', { nodes: item.nodeCount, edges: item.edgeCount })}
              </TableCell>
              <TableCell className="text-muted-foreground">
                <span title={formatStamp(item.updatedAt, i18n.language)}>
                  {formatRelative(Date.parse(item.updatedAt), i18n.language)}
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function MobileCards({ items, onOpen }: { items: NetworkListItem[]; onOpen: (id: string) => void }) {
  const { t, i18n } = useTranslation();
  const { selectedSet, toggleOne, onRowClick } = useSelection(items);
  const select = useNetworksUi((state) => state.select);

  return (
    <ul className="space-y-2 overflow-auto p-3">
      {items.map((item) => (
        <li key={item.id}>
          <div
            className={cn(
              'flex gap-3 rounded-md border p-3',
              selectedSet.has(item.id) && 'border-primary bg-accent/40',
            )}
          >
            <Checkbox
              checked={selectedSet.has(item.id)}
              onCheckedChange={() => toggleOne(item.id)}
              aria-label={item.name}
              className="mt-1"
            />
            <button
              type="button"
              className="min-w-0 flex-1 text-left"
              onClick={(event) => {
                if (event.shiftKey) {
                  onRowClick(event, item.id);
                  return;
                }
                select([item.id], item.id);
              }}
            >
              <p className="font-medium">{item.name}</p>
              {item.description ? (
                <p className="line-clamp-2 text-sm text-muted-foreground">{item.description}</p>
              ) : null}
              <div className="mt-2">
                <StatusBadges item={item} />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {t('networks.list.counts', { nodes: item.nodeCount, edges: item.edgeCount })}
                {' · '}
                {formatRelative(Date.parse(item.updatedAt), i18n.language)}
              </p>
              <TagRow tags={item.tags} />
            </button>
            <Button type="button" size="sm" variant="outline" onClick={() => onOpen(item.id)}>
              {t('networks.ribbon.open')}
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}

function TagRow({ tags }: { tags?: string[] }) {
  if (!tags?.length) return null;
  return (
    <span className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Badge key={tag} variant="outline">
          {tag}
        </Badge>
      ))}
    </span>
  );
}
