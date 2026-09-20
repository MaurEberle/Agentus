import type { KeyboardEvent, MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import { Copy } from 'lucide-react';
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
import { cn } from '@/lib/utils';
import { durationMs, formatDateTime, formatDuration, outcomeBadgeVariant, shortId } from '@/modules/history/model/format';
import type { RunSummary } from '@/modules/history/model/types';
import { useHistoryUi } from '@/modules/history/store';

function rangeIds(visibleIds: string[], fromId: string | null, toId: string): string[] {
  if (!fromId) return [toId];
  const from = visibleIds.indexOf(fromId);
  const to = visibleIds.indexOf(toId);
  if (from < 0 || to < 0) return [toId];
  return visibleIds.slice(Math.min(from, to), Math.max(from, to) + 1);
}

export function RunList({
  items,
  loading,
  activeId,
  onOpen,
}: {
  items: RunSummary[];
  loading: boolean;
  activeId?: string;
  onOpen: (id: string) => void;
}) {
  const isDesktop = useMediaQuery('(min-width: 768px)');
  if (loading) {
    return (
      <div className="space-y-2 p-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }
  return isDesktop ? (
    <DesktopTable items={items} activeId={activeId} onOpen={onOpen} />
  ) : (
    <MobileCards items={items} activeId={activeId} onOpen={onOpen} />
  );
}

function useSelection(items: RunSummary[]) {
  const selectedIds = useHistoryUi((state) => state.selectedIds);
  const anchorId = useHistoryUi((state) => state.anchorId);
  const select = useHistoryUi((state) => state.select);
  const visibleIds = items.map((item) => item.runId);
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

function DesktopTable({
  items,
  activeId,
  onOpen,
}: {
  items: RunSummary[];
  activeId?: string;
  onOpen: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const { selectedSet, allVisibleSelected, onRowClick, toggleOne, toggleAll } = useSelection(items);

  return (
    <Table className="table-fixed">
      <TableHeader>
        <TableRow>
          <TableHead className="w-8">
            <Checkbox checked={allVisibleSelected} onCheckedChange={() => toggleAll()} aria-label={t('history.list.selectAll')} />
          </TableHead>
          <TableHead className="w-24">{t('history.list.runId')}</TableHead>
          <TableHead>{t('history.list.network')}</TableHead>
          <TableHead className="w-36">{t('history.list.started')}</TableHead>
          <TableHead className="w-16">{t('history.list.duration')}</TableHead>
          <TableHead className="w-28">{t('history.list.outcome')}</TableHead>
          <TableHead className="w-24">{t('history.list.error')}</TableHead>
          <TableHead className="w-40">{t('history.list.models')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => {
          const duration = durationMs(item.startedAt, item.endedAt);
          return (
            <TableRow
              key={item.runId}
              data-state={selectedSet.has(item.runId) || activeId === item.runId ? 'selected' : undefined}
              className={cn('cursor-pointer', activeId === item.runId && 'bg-accent/60')}
              onClick={(event) => {
                onRowClick(event, item.runId);
                if (!event.shiftKey && !event.metaKey && !event.ctrlKey) onOpen(item.runId);
              }}
              onKeyDown={(event: KeyboardEvent<HTMLTableRowElement>) => {
                if (event.key === 'Enter') onOpen(item.runId);
              }}
              tabIndex={0}
            >
              <TableCell onClick={(event) => event.stopPropagation()}>
                <Checkbox
                  checked={selectedSet.has(item.runId)}
                  onCheckedChange={() => toggleOne(item.runId)}
                  aria-label={item.runId}
                />
              </TableCell>
              <TableCell>
                <IdCell id={item.runId} />
              </TableCell>
              <TableCell className="truncate font-medium" title={item.networkName}>
                {item.networkName}
              </TableCell>
              <TableCell className="whitespace-nowrap text-xs">{formatDateTime(item.startedAt, i18n.language)}</TableCell>
              <TableCell className="tabular-nums">{duration === null ? '—' : formatDuration(duration)}</TableCell>
              <TableCell>
                <OutcomeCell item={item} />
              </TableCell>
              <TableCell className="max-w-[12rem] truncate text-xs text-muted-foreground">
                {item.errorMessage ?? '—'}
              </TableCell>
              <TableCell className="w-40 max-w-[10rem]">
                <div className="flex max-w-full flex-col gap-0.5">
                  {item.models.map((model) => (
                    <Badge
                      key={`${model.provider}:${model.model}`}
                      variant="outline"
                      title={model.model}
                      className="block max-w-full truncate font-mono text-[10px]"
                    >
                      {model.model}
                    </Badge>
                  ))}
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function MobileCards({
  items,
  activeId,
  onOpen,
}: {
  items: RunSummary[];
  activeId?: string;
  onOpen: (id: string) => void;
}) {
  const { i18n } = useTranslation();
  const { selectedSet, toggleOne } = useSelection(items);
  return (
    <ul className="space-y-2 p-1">
      {items.map((item) => {
        const duration = durationMs(item.startedAt, item.endedAt);
        return (
          <li key={item.runId}>
            <div
              className={cn(
                'flex gap-2 rounded-md border p-3',
                activeId === item.runId && 'border-primary',
              )}
            >
              <Checkbox checked={selectedSet.has(item.runId)} onCheckedChange={() => toggleOne(item.runId)} />
              <button type="button" className="min-w-0 flex-1 text-left" onClick={() => onOpen(item.runId)}>
                <p className="font-medium">{item.networkName}</p>
                <p className="text-xs text-muted-foreground">
                  {shortId(item.runId)} · {formatDateTime(item.startedAt, i18n.language)}
                  {duration !== null ? ` · ${formatDuration(duration)}` : ''}
                </p>
                <div className="mt-1">
                  <OutcomeCell item={item} />
                </div>
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function IdCell({ id }: { id: string }) {
  const { t } = useTranslation();
  return (
    <span className="inline-flex items-center gap-1 font-mono text-xs">
      {shortId(id)}
      <Button
        type="button"
        size="icon"
        variant="ghost"
        className="size-6"
        onClick={(event) => {
          event.stopPropagation();
          void navigator.clipboard.writeText(id);
        }}
      >
        <Copy className="size-3" />
        <span className="sr-only">{t('history.copy')}</span>
      </Button>
    </span>
  );
}

function OutcomeCell({ item }: { item: RunSummary }) {
  const { t } = useTranslation();
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <Badge variant={outcomeBadgeVariant(item.outcome)}>{t(`history.outcome.${item.outcome}`)}</Badge>
      {item.outcome === 'running' ? (
        <Button asChild size="sm" variant="link" className="h-auto px-0" onClick={(event) => event.stopPropagation()}>
          <Link to="/monitoring">{t('history.list.live')}</Link>
        </Button>
      ) : null}
    </span>
  );
}
