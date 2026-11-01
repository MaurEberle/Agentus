import { useRef, useState, type DragEvent, type KeyboardEvent, type MouseEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Skeleton } from '@/components/ui/skeleton';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { formatRelative } from '@/lib/relativeTime';
import type { NetworkListItem } from '@/modules/dashboard/model';
import { validationBadgeVariant } from '@/modules/dashboard/model';
import { formatStamp } from '@/modules/networks/model/format';
import { rangeIds } from '@/modules/networks/model/filter';
import {
  clampColumnWidth,
  columnMax,
  columnMin,
  loadNetworkColumns,
  saveNetworkColumns,
  type NetworkColumnId,
  type NetworkColumnLayout,
} from '@/modules/networks/list/networkColumns';
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
      <div className="min-h-0 flex-1 space-y-2 overflow-auto p-3">
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
  const [layout, setLayout] = useState<NetworkColumnLayout>(loadNetworkColumns);
  const layoutRef = useRef(layout);
  layoutRef.current = layout;
  const dragFrom = useRef<NetworkColumnId | null>(null);
  const dropRef = useRef<{ id: NetworkColumnId; side: 'before' | 'after' } | null>(null);
  const [drop, setDrop] = useState<{ id: NetworkColumnId; side: 'before' | 'after' } | null>(null);
  const [dragging, setDragging] = useState<NetworkColumnId | null>(null);

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Enter') return;
    const only = [...selectedSet];
    if (only.length === 1) onOpen(only[0]);
  }

  function commit(next: NetworkColumnLayout) {
    const normalized = { order: next.order, widths: { ...next.widths } };
    layoutRef.current = normalized;
    setLayout(normalized);
    saveNetworkColumns(normalized);
  }

  function setWidth(id: NetworkColumnId, width: number) {
    commit({
      ...layoutRef.current,
      widths: { ...layoutRef.current.widths, [id]: clampColumnWidth(id, width) },
    });
  }

  function placeDrop(id: NetworkColumnId, side: 'before' | 'after') {
    dropRef.current = { id, side };
    setDrop({ id, side });
  }

  function finishDrag(target?: NetworkColumnId) {
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

  function beginResize(event: ReactPointerEvent<HTMLElement>, id: NetworkColumnId) {
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
    <div
      tabIndex={0}
      onKeyDown={onKey}
      className="min-h-0 min-w-0 flex-1 overflow-auto outline-none"
    >
      <div
        role="table"
        className="grid w-max min-w-full text-sm"
        style={{ gridTemplateColumns: template, contain: 'paint' }}
      >
        <div role="row" className="col-span-full grid grid-cols-subgrid items-center border-b hover:bg-transparent">
          <div className="px-3">
            <Checkbox
              checked={allVisibleSelected}
              onCheckedChange={() => toggleAll()}
              aria-label={t('networks.list.selectAll')}
            />
          </div>
          {layout.order.map((id) => (
            <ColumnHead
              key={id}
              id={id}
              label={t(`networks.list.${id}`)}
              width={layout.widths[id]}
              dragging={dragging === id}
              dropSide={drop?.id === id ? drop.side : null}
              resizeLabel={t('networks.list.resize', { column: t(`networks.list.${id}`) })}
              moveLabel={t('networks.list.move', { column: t(`networks.list.${id}`) })}
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
        </div>
        {items.map((item) => (
          <div
            key={item.id}
            role="row"
            data-state={selectedSet.has(item.id) ? 'selected' : undefined}
            className="col-span-full grid cursor-pointer grid-cols-subgrid items-center border-b hover:bg-muted/50 data-[state=selected]:bg-muted"
            onClick={(event) => onRowClick(event, item.id)}
            onDoubleClick={() => onOpen(item.id)}
          >
            <div className="px-3" onClick={(event) => event.stopPropagation()}>
              <Checkbox
                checked={selectedSet.has(item.id)}
                onCheckedChange={() => toggleOne(item.id)}
                aria-label={item.name}
              />
            </div>
            {layout.order.map((id) => (
              <NetworkCell key={id} id={id} item={item} locale={i18n.language} />
            ))}
          </div>
        ))}
      </div>
    </div>
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
  id: NetworkColumnId;
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

function NetworkCell({ id, item, locale }: { id: NetworkColumnId; item: NetworkListItem; locale: string }) {
  const { t } = useTranslation();
  if (id === 'name') {
    return (
      <div className="min-w-0 overflow-hidden px-3 py-2">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="truncate font-medium" title={item.name}>{item.name}</span>
          <TagRow tags={item.tags} />
        </div>
      </div>
    );
  }
  if (id === 'description') {
    const text = item.description || '—';
    return (
      <div className="min-w-0 truncate px-3 py-2 text-muted-foreground" title={text}>
        {text}
      </div>
    );
  }
  if (id === 'status') {
    return (
      <div className="min-w-0 overflow-hidden px-3 py-2">
        <StatusBadges item={item} />
      </div>
    );
  }
  if (id === 'graph') {
    return (
      <div className="min-w-0 truncate px-3 py-2 text-muted-foreground">
        {t('networks.list.counts', { nodes: item.nodeCount, edges: item.edgeCount })}
      </div>
    );
  }
  const stamp = formatStamp(item.updatedAt, locale);
  return (
    <div className="min-w-0 truncate px-3 py-2 text-muted-foreground" title={stamp}>
      {formatRelative(Date.parse(item.updatedAt), locale)}
    </div>
  );
}

function MobileCards({ items, onOpen }: { items: NetworkListItem[]; onOpen: (id: string) => void }) {
  const { t, i18n } = useTranslation();
  const { selectedSet, toggleOne, onRowClick } = useSelection(items);
  const select = useNetworksUi((state) => state.select);

  return (
    <ul className="min-h-0 flex-1 space-y-2 overflow-auto p-3">
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
