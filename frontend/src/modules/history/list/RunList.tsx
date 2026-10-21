import { useRef, useState, type DragEvent, type KeyboardEvent, type MouseEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { Link } from 'react-router-dom';
import { Copy } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Skeleton } from '@/components/ui/skeleton';
import { HistoryGrid, HistoryRow } from '@/modules/history/HistoryGrid';
import {
  clampColumnWidth,
  columnMax,
  columnMin,
  loadRunColumns,
  saveRunColumns,
  type RunColumnId,
  type RunColumnLayout,
} from '@/modules/history/list/runColumns';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { cn } from '@/lib/utils';
import { durationMs, formatDateTime, formatDuration, outcomeBadgeVariant, shortId } from '@/modules/history/model/format';
import { formatRunLogMessage } from '@/modules/monitoring/model/logMessage';
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

const cellClass = 'min-w-0 overflow-hidden text-ellipsis whitespace-nowrap px-3 py-2';

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
  const [layout, setLayout] = useState<RunColumnLayout>(loadRunColumns);
  const layoutRef = useRef(layout);
  layoutRef.current = layout;
  const dragFrom = useRef<RunColumnId | null>(null);
  const dropRef = useRef<{ id: RunColumnId; side: 'before' | 'after' } | null>(null);
  const [drop, setDrop] = useState<{ id: RunColumnId; side: 'before' | 'after' } | null>(null);
  const [dragging, setDragging] = useState<RunColumnId | null>(null);

  function commit(next: RunColumnLayout) {
    const normalized = {
      order: next.order,
      widths: { ...next.widths },
    };
    layoutRef.current = normalized;
    setLayout(normalized);
    saveRunColumns(normalized);
  }

  function setWidth(id: RunColumnId, width: number) {
    commit({
      ...layoutRef.current,
      widths: { ...layoutRef.current.widths, [id]: clampColumnWidth(id, width) },
    });
  }

  function placeDrop(id: RunColumnId, side: 'before' | 'after') {
    dropRef.current = { id, side };
    setDrop({ id, side });
  }

  function finishDrag(target?: RunColumnId) {
    const from = dragFrom.current;
    const mark = dropRef.current;
    dragFrom.current = null;
    dropRef.current = null;
    setDragging(null);
    setDrop(null);
    if (!from || !target || !mark || from === target) return;
    const without = layoutRef.current.order.filter((item) => item !== from);
    let index = without.indexOf(target);
    if (index < 0) return;
    if (mark.side === 'after') index += 1;
    without.splice(index, 0, from);
    commit({ ...layoutRef.current, order: without });
  }

  function beginResize(event: ReactPointerEvent<HTMLElement>, id: RunColumnId) {
    event.preventDefault();
    event.stopPropagation();
    const handle = event.currentTarget;
    const startX = event.clientX;
    const startW = layoutRef.current.widths[id];
    const rtl = document.documentElement.dir === 'rtl';
    handle.setPointerCapture(event.pointerId);
    const move = (ev: PointerEvent) => {
      const delta = rtl ? startX - ev.clientX : ev.clientX - startX;
      setWidth(id, startW + delta);
    };
    const up = (ev: PointerEvent) => {
      if (handle.hasPointerCapture(ev.pointerId)) handle.releasePointerCapture(ev.pointerId);
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', up);
      handle.removeEventListener('pointercancel', up);
    };
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', up);
    handle.addEventListener('pointercancel', up);
  }

  const template = ['2.5rem', ...layout.order.map((id) => `${layout.widths[id]}px`)].join(' ');

  return (
    <HistoryGrid columns={template}>
      <HistoryRow className="hover:bg-transparent">
        <div className="px-3">
          <Checkbox checked={allVisibleSelected} onCheckedChange={() => toggleAll()} aria-label={t('history.list.selectAll')} />
        </div>
        {layout.order.map((id) => (
          <ColumnHead
            key={id}
            id={id}
            label={t(`history.list.${id}`)}
            width={layout.widths[id]}
            dragging={dragging === id}
            dropSide={drop?.id === id ? drop.side : null}
            resizeLabel={t('history.list.resize', { column: t(`history.list.${id}`) })}
            moveLabel={t('history.list.move', { column: t(`history.list.${id}`) })}
            onDragStart={() => {
              dragFrom.current = id;
              setDragging(id);
            }}
            onDragOver={(side) => placeDrop(id, side)}
            onDrop={() => finishDrag(id)}
            onDragEnd={() => finishDrag()}
            onResizeStart={(event) => beginResize(event, id)}
            onResizeKey={(next) => setWidth(id, next)}
          />
        ))}
      </HistoryRow>
      {items.map((item) => {
        const duration = durationMs(item.startedAt, item.endedAt);
        const errorText = item.errorMessage ? formatRunLogMessage(item.errorMessage, t) : '—';
        return (
          <HistoryRow
            key={item.runId}
            data-state={selectedSet.has(item.runId) || activeId === item.runId ? 'selected' : undefined}
            className={cn('cursor-pointer', activeId === item.runId && 'bg-accent/60')}
            onClick={(event) => {
              onRowClick(event, item.runId);
              if (!event.shiftKey && !event.metaKey && !event.ctrlKey) onOpen(item.runId);
            }}
            onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => {
              if (event.key === 'Enter') onOpen(item.runId);
            }}
            tabIndex={0}
          >
            <div className="px-3" onClick={(event) => event.stopPropagation()}>
              <Checkbox
                checked={selectedSet.has(item.runId)}
                onCheckedChange={() => toggleOne(item.runId)}
                aria-label={item.runId}
              />
            </div>
            {layout.order.map((id) => (
              <RunCell
                key={id}
                id={id}
                item={item}
                duration={duration}
                errorText={errorText}
                locale={i18n.language}
              />
            ))}
          </HistoryRow>
        );
      })}
    </HistoryGrid>
  );
}

function ColumnHead({
  id,
  label,
  width,
  dragging,
  dropSide,
  resizeLabel,
  moveLabel,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
  onResizeStart,
  onResizeKey,
}: {
  id: RunColumnId;
  label: string;
  width: number;
  dragging: boolean;
  dropSide: 'before' | 'after' | null;
  resizeLabel: string;
  moveLabel: string;
  onDragStart: () => void;
  onDragOver: (side: 'before' | 'after') => void;
  onDrop: () => void;
  onDragEnd: () => void;
  onResizeStart: (event: ReactPointerEvent<HTMLElement>) => void;
  onResizeKey: (width: number) => void;
}) {
  function sideFrom(event: DragEvent<HTMLElement>): 'before' | 'after' {
    const rect = event.currentTarget.getBoundingClientRect();
    const rtl = document.documentElement.dir === 'rtl';
    const towardStart = rtl ? event.clientX > rect.left + rect.width / 2 : event.clientX < rect.left + rect.width / 2;
    return towardStart ? 'before' : 'after';
  }

  return (
    <div
      role="columnheader"
      draggable
      title={label}
      aria-label={moveLabel}
      onDragStart={(event) => {
        if ((event.target as HTMLElement).closest('[data-col-resize]')) {
          event.preventDefault();
          return;
        }
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', id);
        onDragStart();
      }}
      onDragOver={(event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        onDragOver(sideFrom(event));
      }}
      onDrop={(event) => {
        event.preventDefault();
        onDrop();
      }}
      onDragEnd={onDragEnd}
      className={cn(
        'relative flex h-10 min-w-0 cursor-grab select-none items-center px-3 text-xs font-medium text-muted-foreground active:cursor-grabbing',
        dragging && 'opacity-50',
        dropSide === 'before' && "before:absolute before:inset-y-1 before:start-0 before:w-0.5 before:bg-primary before:content-['']",
        dropSide === 'after' && "after:absolute after:inset-y-1 after:end-0 after:w-0.5 after:bg-primary after:content-['']",
      )}
    >
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span
        data-col-resize
        role="separator"
        aria-orientation="vertical"
        aria-label={resizeLabel}
        aria-valuemin={columnMin(id)}
        aria-valuemax={columnMax()}
        aria-valuenow={width}
        tabIndex={0}
        draggable={false}
        className="absolute inset-y-0 end-0 z-10 flex w-3 cursor-col-resize touch-none items-center justify-center"
        onPointerDown={onResizeStart}
        onMouseDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
        onClick={(event) => event.stopPropagation()}
        onDragStart={(event) => event.preventDefault()}
        onKeyDown={(event) => {
          if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
          event.preventDefault();
          event.stopPropagation();
          const step = event.shiftKey ? 48 : 16;
          const rtl = document.documentElement.dir === 'rtl';
          const sign = (event.key === 'ArrowRight' ? 1 : -1) * (rtl ? -1 : 1);
          onResizeKey(width + sign * step);
        }}
      >
        <span className="h-4 w-0.5 rounded-full bg-border" />
      </span>
    </div>
  );
}

function RunCell({
  id,
  item,
  duration,
  errorText,
  locale,
}: {
  id: RunColumnId;
  item: RunSummary;
  duration: number | null;
  errorText: string;
  locale: string;
}) {
  if (id === 'runId') {
    return (
      <div className={cellClass}>
        <IdCell id={item.runId} />
      </div>
    );
  }
  if (id === 'network') {
    return (
      <div className={cn(cellClass, 'font-medium')} title={item.networkName}>
        {item.networkName}
      </div>
    );
  }
  if (id === 'started') {
    return <div className={cn(cellClass, 'text-xs')}>{formatDateTime(item.startedAt, locale)}</div>;
  }
  if (id === 'duration') {
    return <div className={cn(cellClass, 'tabular-nums')}>{duration === null ? '—' : formatDuration(duration)}</div>;
  }
  if (id === 'outcome') {
    return (
      <div className={cn(cellClass, 'overflow-hidden')}>
        <OutcomeCell item={item} />
      </div>
    );
  }
  if (id === 'models') {
    return (
      <div className="min-w-0 overflow-hidden px-3 py-2">
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
      </div>
    );
  }
  return (
    <div className={cn(cellClass, 'text-xs text-muted-foreground')} title={errorText}>
      {errorText}
    </div>
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
