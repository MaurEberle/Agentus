import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { notify } from '@/lib/notifications';
import type { NetworkListItem } from '@/modules/dashboard/model';
import { ExportCancelled, saveExportFile } from '@/lib/saveFile';
import {
  deleteNetworks,
  duplicateNetwork,
  exportNetwork,
  importNetwork,
  listNetworkSummaries,
  renameNetwork,
  saveNetworkTags,
  setLibraryActive,
} from '@/modules/networks/api';
import { DetailPanel } from '@/modules/networks/detail/DetailPanel';
import { DeleteDialog } from '@/modules/networks/dialogs/DeleteDialog';
import { ExportDialog } from '@/modules/networks/dialogs/ExportDialog';
import { ImportDialog } from '@/modules/networks/dialogs/ImportDialog';
import { RenameDialog } from '@/modules/networks/dialogs/RenameDialog';
import { TagsDialog } from '@/modules/networks/dialogs/TagsDialog';
import { FilterBar } from '@/modules/networks/filters/FilterBar';
import { NetworkList } from '@/modules/networks/list/NetworkList';
import { applyNetworkFilters, sharedTags, uniqueTags } from '@/modules/networks/model/filter';
import { exportFileStem, exportStamp } from '@/modules/networks/model/importDoc';
import { zipStore } from '@/modules/networks/model/zip';
import { LibraryRibbon } from '@/modules/networks/ribbon/Ribbon';
import { useNetworksUi } from '@/modules/networks/store';
import type { AgentNetworkDocument } from '@/modules/network/model/document';
import { ModuleLoading } from '@/components/layout/ModuleLoading';

const DETAIL_MIN = 320;

function useDetailWidth() {
  const [value, setValue] = useState(() => {
    try {
      const raw = Number(window.localStorage.getItem('agentus.networks.detailWidth'));
      if (Number.isFinite(raw) && raw >= DETAIL_MIN) return raw;
    } catch {
      /* ignore private mode */
    }
    return DETAIL_MIN;
  });
  const setWidth = useCallback((next: number) => {
    const clamped = Math.max(DETAIL_MIN, Math.round(next));
    setValue(clamped);
    try {
      window.localStorage.setItem('agentus.networks.detailWidth', String(clamped));
    } catch {
      /* ignore quota */
    }
  }, []);
  return [value, setWidth] as const;
}

export function NetworksModule() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const query = useQuery({ queryKey: ['networks'], queryFn: listNetworkSummaries });
  const items = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const filterQuery = useNetworksUi((state) => state.query);
  const tagFilter = useNetworksUi((state) => state.tagFilter);
  const onlyValid = useNetworksUi((state) => state.onlyValid);
  const onlyActive = useNetworksUi((state) => state.onlyActive);
  const sortKey = useNetworksUi((state) => state.sortKey);
  const sortDir = useNetworksUi((state) => state.sortDir);
  const selectedIds = useNetworksUi((state) => state.selectedIds);
  const select = useNetworksUi((state) => state.select);
  const clearSelection = useNetworksUi((state) => state.clearSelection);
  const pruneSelection = useNetworksUi((state) => state.pruneSelection);
  const setQuery = useNetworksUi((state) => state.setQuery);
  const filtered = useMemo(
    () => applyNetworkFilters(items, { query: filterQuery, tagFilter, onlyValid, onlyActive, sortKey, sortDir }),
    [filterQuery, items, onlyActive, onlyValid, sortDir, sortKey, tagFilter],
  );
  const selected = useMemo(
    () => selectedIds.map((id) => items.find((item) => item.id === id)).filter((item): item is NetworkListItem => Boolean(item)),
    [items, selectedIds],
  );
  const tags = useMemo(() => uniqueTags(items), [items]);
  const seedTags = useMemo(() => sharedTags(selected), [selected]);
  const filtersOn = Boolean(filterQuery.trim() || tagFilter.length || onlyValid || onlyActive);

  const [busy, setBusy] = useState(false);
  const [renameItem, setRenameItem] = useState<NetworkListItem | null>(null);
  const [tagsOpen, setTagsOpen] = useState(false);
  const [deleteItems, setDeleteItems] = useState<NetworkListItem[] | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [detailWidth, setDetailWidth] = useDetailWidth();
  const detailDrag = useRef({ x: 0, width: DETAIL_MIN });
  const detailWidthRef = useRef(detailWidth);
  detailWidthRef.current = detailWidth;
  const libraryRowRef = useRef<HTMLDivElement>(null);
  const detailLimit = useCallback(() => {
    const row = libraryRowRef.current;
    if (!row) return detailWidthRef.current;
    return Math.max(DETAIL_MIN, row.clientWidth - 280);
  }, []);

  useEffect(() => {
    pruneSelection(items.map((item) => item.id));
  }, [items, pruneSelection]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      if (renameItem || tagsOpen || deleteItems || exportOpen || importOpen) return;
      clearSelection();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [clearSelection, deleteItems, exportOpen, importOpen, renameItem, tagsOpen]);

  function openEditor(id?: string) {
    navigate(id ? `/network/${id}` : '/network');
  }

  async function run(action: () => Promise<void>, okKey?: string, values?: Record<string, string>) {
    setBusy(true);
    try {
      await action();
      if (okKey) notify({ titleKey: okKey, values, variant: 'success' });
    } catch (error) {
      if (error instanceof ExportCancelled) return;
      notify({ titleKey: 'networks.notify.error', variant: 'error' });
    } finally {
      setBusy(false);
    }
  }

  async function onDuplicate() {
    const item = selected[0];
    if (!item) return;
    await run(async () => {
      const copy = await duplicateNetwork(item.id);
      const name = `${item.name} ${t('networks.copySuffix')}`.trim();
      if (copy.name !== name) await renameNetwork(copy.id as string, { name });
      select([copy.id as string], copy.id as string);
    }, 'networks.notify.duplicated');
  }

  async function onActivate() {
    const item = selected[0];
    if (!item) return;
    await run(async () => {
      await setLibraryActive(item.id);
    });
  }

  async function confirmExport() {
    if (selected.length === 0) return;
    await run(async () => {
      const stamp = exportStamp();
      const used = new Set<string>();
      const fileName = (name: string) => {
        const base = `${exportFileStem(name)}-${stamp}`;
        let next = `${base}.json`;
        let index = 2;
        while (used.has(next)) {
          next = `${base}-${index}.json`;
          index += 1;
        }
        used.add(next);
        return next;
      };
      if (selected.length === 1) {
        const payload = await exportNetwork(selected[0].id);
        const written = await saveExportFile(
          fileName(selected[0].name),
          new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: 'application/json' }),
        );
        if (!written) throw new ExportCancelled();
      } else {
        const files = [];
        for (const item of selected) {
          const payload = await exportNetwork(item.id);
          files.push({
            name: fileName(item.name),
            data: new TextEncoder().encode(`${JSON.stringify(payload, null, 2)}\n`),
          });
        }
        const written = await saveExportFile(`networks-${stamp}.zip`, zipStore(files));
        if (!written) throw new ExportCancelled();
      }
      setExportOpen(false);
    }, 'networks.notify.exported');
  }

  async function importDocuments(documents: AgentNetworkDocument[]) {
    for (const document of documents) {
      await importNetwork(document);
    }
  }

  function confirmImport(documents: AgentNetworkDocument[]) {
    void run(async () => {
      await importDocuments(documents);
      setImportOpen(false);
    }, 'networks.notify.imported', { count: String(documents.length) });
  }

  const emptyLibrary = !query.isLoading && items.length === 0;
  const emptyFilter = !query.isLoading && items.length > 0 && filtered.length === 0;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <LibraryRibbon
        selected={selected}
        busy={busy}
        handlers={{
          onNew: () => openEditor(),
          onOpen: () => selected[0] && openEditor(selected[0].id),
          onDuplicate: () => void onDuplicate(),
          onRename: () => setRenameItem(selected[0] ?? null),
          onTags: () => setTagsOpen(true),
          onActivate: () => void onActivate(),
          onDelete: () => setDeleteItems(selected),
          onImport: () => setImportOpen(true),
          onExport: () => setExportOpen(true),
          onRefresh: () => void query.refetch(),
        }}
      />
      <FilterBar tags={tags} />
      {query.isError ? (
        <Alert variant="destructive" className="m-3">
          <AlertTitle>{t('networks.error.title')}</AlertTitle>
          <AlertDescription className="flex items-center gap-2">
            {t('networks.error.body')}
            <Button type="button" size="sm" variant="outline" loading={query.isFetching} onClick={() => void query.refetch()}>
              {t('networks.ribbon.refresh')}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      {emptyLibrary ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
          <p className="text-sm text-muted-foreground">{t('networks.empty.library')}</p>
          <div className="flex gap-2">
            <Button type="button" onClick={() => openEditor()}>
              {t('networks.ribbon.new')}
            </Button>
            <Button type="button" variant="outline" onClick={() => setImportOpen(true)}>
              {t('networks.ribbon.import')}
            </Button>
          </div>
        </div>
      ) : query.isLoading ? (
        <ModuleLoading />
      ) : emptyFilter ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
          <p className="text-sm text-muted-foreground">{t('networks.empty.filter')}</p>
          {filtersOn ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setQuery('');
                useNetworksUi.setState({ tagFilter: [], onlyValid: false, onlyActive: false });
              }}
            >
              {t('networks.empty.clearFilters')}
            </Button>
          ) : null}
        </div>
      ) : (
        <div ref={libraryRowRef} className="flex min-h-0 flex-1">
          <div className="min-h-0 min-w-0 flex-1">
            <NetworkList items={filtered} loading={false} onOpen={openEditor} />
          </div>
          {isDesktop ? (
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label={t('networks.detail.resize')}
              aria-valuenow={detailWidth}
              aria-valuemin={DETAIL_MIN}
              tabIndex={0}
              className="hidden w-4 shrink-0 cursor-col-resize touch-none items-center justify-center self-stretch rounded-sm hover:bg-muted/50 focus-visible:bg-muted/50 md:flex"
              onPointerDown={(event) => {
                detailDrag.current = { x: event.clientX, width: detailWidth };
                event.currentTarget.setPointerCapture(event.pointerId);
              }}
              onPointerMove={(event) => {
                if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
                const next = detailDrag.current.width - (event.clientX - detailDrag.current.x);
                setDetailWidth(Math.min(detailLimit(), next));
              }}
              onKeyDown={(event) => {
                if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
                event.preventDefault();
                const step = event.shiftKey ? 48 : 16;
                const delta = event.key === 'ArrowLeft' ? step : -step;
                setDetailWidth(Math.min(detailLimit(), detailWidth + delta));
              }}
            >
              <span className="h-8 w-1 rounded-full bg-border" aria-hidden />
            </div>
          ) : null}
          {isDesktop ? (
            <aside className="hidden h-full min-h-0 shrink-0 flex-col md:flex" style={{ width: detailWidth }}>
              <DetailPanel items={selected} onOpen={openEditor} layoutWidth={detailWidth} />
            </aside>
          ) : null}
        </div>
      )}
      {!isDesktop ? (
        <Sheet open={selected.length === 1} onOpenChange={(open) => !open && clearSelection()}>
          <SheetContent side="bottom" closeLabel={t('networks.dialog.close')} className="h-[70vh] overflow-auto">
            <SheetHeader>
              <SheetTitle>{t('networks.detail.title')}</SheetTitle>
            </SheetHeader>
            <DetailPanel items={selected} onOpen={openEditor} />
          </SheetContent>
        </Sheet>
      ) : null}
      <RenameDialog
        item={renameItem}
        busy={busy}
        onClose={() => setRenameItem(null)}
        onSave={(patch) => {
          if (!renameItem) return;
          void run(async () => {
            await renameNetwork(renameItem.id, patch);
            setRenameItem(null);
          }, 'networks.notify.renamed');
        }}
      />
      <TagsDialog
        open={tagsOpen}
        count={selected.length}
        busy={busy}
        initialTags={seedTags}
        suggestions={tags}
        onClose={() => setTagsOpen(false)}
        onSave={(nextTags) => {
          void run(async () => {
            await saveNetworkTags(selected, seedTags, nextTags);
            setTagsOpen(false);
          }, 'networks.notify.tagged');
        }}
      />
      <DeleteDialog
        items={deleteItems}
        busy={busy}
        onClose={() => setDeleteItems(null)}
        onConfirm={() => {
          const ids = (deleteItems ?? []).filter((item) => !item.isRunning).map((item) => item.id);
          if (ids.length === 0) return;
          void run(async () => {
            await deleteNetworks(ids);
            setDeleteItems(null);
            clearSelection();
          }, 'networks.notify.deleted');
        }}
      />
      <ExportDialog
        open={exportOpen}
        items={selected.map((item) => ({
          name: item.name,
          nodeCount: item.nodeCount,
          edgeCount: item.edgeCount,
        }))}
        busy={busy}
        onClose={() => setExportOpen(false)}
        onConfirm={() => void confirmExport()}
      />
      <ImportDialog
        open={importOpen}
        multiple
        existingNames={items.map((item) => item.name)}
        busy={busy}
        onClose={() => setImportOpen(false)}
        onImport={confirmImport}
      />
    </div>
  );
}
