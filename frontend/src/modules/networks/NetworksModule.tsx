import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { notify } from '@/lib/notifications';
import type { NetworkListItem } from '@/modules/dashboard/model';
import { downloadJson } from '@/modules/network/model/serialize';
import {
  addTags,
  deleteNetworks,
  duplicateNetwork,
  exportNetwork,
  importNetwork,
  listNetworkSummaries,
  renameNetwork,
  setLibraryActive,
} from '@/modules/networks/api';
import { DetailPanel } from '@/modules/networks/detail/DetailPanel';
import { DeleteDialog } from '@/modules/networks/dialogs/DeleteDialog';
import { ImportCollisionDialog, type CollisionRow } from '@/modules/networks/dialogs/ImportCollisionDialog';
import { RenameDialog } from '@/modules/networks/dialogs/RenameDialog';
import { TagsDialog } from '@/modules/networks/dialogs/TagsDialog';
import { FilterBar } from '@/modules/networks/filters/FilterBar';
import { NetworkList } from '@/modules/networks/list/NetworkList';
import { applyNetworkFilters, uniqueTags } from '@/modules/networks/model/filter';
import { exportFileStem, exportStamp, isImportFail, parseImportJson } from '@/modules/networks/model/importDoc';
import { downloadBlob, zipStore } from '@/modules/networks/model/zip';
import { LibraryRibbon } from '@/modules/networks/ribbon/Ribbon';
import { useNetworksUi } from '@/modules/networks/store';
import type { AgentNetworkDocument } from '@/modules/network/model/document';

export function NetworksModule() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const fileRef = useRef<HTMLInputElement>(null);
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
  const filtersOn = Boolean(filterQuery.trim() || tagFilter.length || onlyValid || onlyActive);

  const [busy, setBusy] = useState(false);
  const [renameItem, setRenameItem] = useState<NetworkListItem | null>(null);
  const [tagsOpen, setTagsOpen] = useState(false);
  const [deleteItems, setDeleteItems] = useState<NetworkListItem[] | null>(null);
  const [collisions, setCollisions] = useState<CollisionRow[] | null>(null);

  useEffect(() => {
    pruneSelection(items.map((item) => item.id));
  }, [items, pruneSelection]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      if (renameItem || tagsOpen || deleteItems || collisions) return;
      clearSelection();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [clearSelection, collisions, deleteItems, renameItem, tagsOpen]);

  function openEditor(id?: string) {
    navigate(id ? `/network/${id}` : '/network');
  }

  async function run(action: () => Promise<void>, okKey?: string, values?: Record<string, string>) {
    setBusy(true);
    try {
      await action();
      if (okKey) notify({ titleKey: okKey, values, variant: 'success' });
    } catch {
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

  async function onExport() {
    if (selected.length === 0) return;
    await run(async () => {
      const stamp = exportStamp();
      if (selected.length === 1) {
        const payload = await exportNetwork(selected[0].id);
        downloadJson(`${exportFileStem(selected[0].name)}-${stamp}.json`, payload);
        return;
      }
      const files = [];
      for (const item of selected) {
        const payload = await exportNetwork(item.id);
        files.push({
          name: `${exportFileStem(item.name)}-${stamp}.json`,
          data: new TextEncoder().encode(`${JSON.stringify(payload, null, 2)}\n`),
        });
      }
      downloadBlob(`networks-${stamp}.zip`, zipStore(files));
    }, 'networks.notify.exported');
  }

  async function importDocuments(documents: AgentNetworkDocument[]) {
    for (const document of documents) {
      await importNetwork(document);
    }
  }

  async function onFiles(fileList: FileList | null) {
    if (!fileList?.length) return;
    const existing = new Set(items.map((item) => item.name.trim().toLowerCase()));
    const failures: string[] = [];
    let stripped = 0;
    const ready: AgentNetworkDocument[] = [];
    const collisionRows: CollisionRow[] = [];
    for (const file of Array.from(fileList)) {
      try {
        const parsed = parseImportJson(file.name, JSON.parse(await file.text()) as unknown);
        if (isImportFail(parsed)) {
          failures.push(file.name);
          continue;
        }
        if (parsed.strippedSecrets) stripped += 1;
        const key = parsed.document.name.trim().toLowerCase();
        if (existing.has(key)) collisionRows.push({ fileName: file.name, document: parsed.document });
        else {
          existing.add(key);
          ready.push(parsed.document);
        }
      } catch {
        failures.push(file.name);
      }
    }
    if (fileRef.current) fileRef.current.value = '';
    if (failures.length) {
      notify({
        titleKey: 'networks.import.unreadable',
        descriptionKey: 'networks.import.unreadableNames',
        values: { names: failures.join(', ') },
        variant: 'error',
      });
    }
    if (stripped) notify({ titleKey: 'networks.import.secrets', variant: 'warning' });
    if (ready.length) {
      await run(async () => {
        await importDocuments(ready);
      }, 'networks.notify.imported', { count: String(ready.length) });
    }
    if (collisionRows.length) setCollisions(collisionRows);
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
          onImport: () => fileRef.current?.click(),
          onExport: () => void onExport(),
          onRefresh: () => void query.refetch(),
        }}
      />
      <FilterBar tags={tags} />
      <input
        ref={fileRef}
        type="file"
        accept="application/json,.json"
        multiple
        className="hidden"
        onChange={(event) => void onFiles(event.target.files)}
      />
      {query.isError ? (
        <Alert variant="destructive" className="m-3">
          <AlertTitle>{t('networks.error.title')}</AlertTitle>
          <AlertDescription className="flex items-center gap-2">
            {t('networks.error.body')}
            <Button type="button" size="sm" variant="outline" onClick={() => void query.refetch()}>
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
            <Button type="button" variant="outline" onClick={() => fileRef.current?.click()}>
              {t('networks.ribbon.import')}
            </Button>
          </div>
        </div>
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
        <div className="flex min-h-0 flex-1">
          <div className="min-h-0 min-w-0 flex-1">
            <NetworkList items={filtered} loading={query.isLoading} onOpen={openEditor} />
          </div>
          {isDesktop ? (
            <aside className="hidden w-80 shrink-0 overflow-auto border-l md:block">
              <DetailPanel items={selected} onOpen={openEditor} />
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
        onClose={() => setTagsOpen(false)}
        onSave={(nextTags) => {
          void run(async () => {
            await addTags(
              selected.map((item) => item.id),
              nextTags,
            );
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
      <ImportCollisionDialog
        rows={collisions}
        busy={busy}
        onClose={() => setCollisions(null)}
        onConfirm={(accepted) => {
          void run(async () => {
            await importDocuments(accepted.map((row) => row.document));
            setCollisions(null);
          }, accepted.length ? 'networks.notify.imported' : undefined, { count: String(accepted.length) });
        }}
      />
    </div>
  );
}
