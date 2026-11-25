import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronsLeft, ChevronsRight } from 'lucide-react';
import { ReactFlowProvider, useReactFlow } from '@xyflow/react';
import { Link, useBlocker, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { notify } from '@/lib/notifications';
import { useAppStore } from '@/store';
import { ApiError, queryClient } from '@/api/client';
import {
  createNetwork,
  duplicateNetwork,
  getNetwork,
  reindexNetworkKnowledge,
  updateNetwork,
  useEditorNetworkQuery,
  useEditorNetworksQuery,
  validateNetwork,
} from '@/modules/network/api';
import { FlowCanvas } from '@/modules/network/canvas/FlowCanvas';
import { knowledgeWithoutIndex, useNetworkVersionsQuery } from '@/modules/network/versions/api';
import { useVersionPreview } from '@/modules/network/versions/previewStore';
import { VersionPreview } from '@/modules/network/versions/VersionPreview';
import { VersionsSheet } from '@/modules/network/versions/VersionsSheet';
import { Inspector } from '@/modules/network/inspector/Inspector';
import { LoadDialog } from '@/modules/network/library/LoadDialog';
import type { AgentNetworkDocument } from '@/modules/network/model/document';
import { duplicateNodes } from '@/modules/network/model/serialize';
import { saveExportFile } from '@/lib/saveFile';
import { ExportDialog } from '@/modules/networks/dialogs/ExportDialog';
import { ImportDialog } from '@/modules/networks/dialogs/ImportDialog';
import { importNetwork, previewExport } from '@/modules/networks/api';
import { exportFileStem, exportStamp } from '@/modules/networks/model/importDoc';
import { Palette } from '@/modules/network/palette/Palette';
import { ModuleLoading } from '@/components/layout/ModuleLoading';
import { Ribbon } from '@/modules/network/ribbon/Ribbon';
import { validateDocument } from '@/modules/network/validation/validate';
import { useMcpRecipesQuery, useMcpServersQuery } from '@/modules/settings/api';
import {
  editorDeleteSelection,
  editorDuplicateSelection,
  editorNudge,
  useNetworkEditor,
} from '@/modules/network/store';

type DirtyAction = 'new' | 'load' | 'library' | 'leave';

/** How a save writes (fix/netz-versionen/entwurf.md, 6 and 8). */
type SaveOptions = {
  /** False writes into the current version. */
  newVersion?: boolean;
  note?: string;
  /** Skip the revision check: the user chose to save over another writer's change. */
  force?: boolean;
};

const INSPECTOR_MIN = 320;

function useLocalWidth(key: string, fallback: number) {
  const [value, setValue] = useState(() => {
    try {
      const raw = Number(window.localStorage.getItem(key));
      if (Number.isFinite(raw) && raw >= fallback) return raw;
    } catch {
      /* ignore private mode */
    }
    return fallback;
  });
  const setWidth = useCallback(
    (next: number) => {
      const clamped = Math.max(fallback, Math.round(next));
      setValue(clamped);
      try {
        window.localStorage.setItem(key, String(clamped));
      } catch {
        /* ignore quota */
      }
    },
    [fallback, key],
  );
  return [value, setWidth] as const;
}

function useLocalFlag(key: string, fallback = false) {
  const [value, setValue] = useState(() => {
    try {
      return window.localStorage.getItem(key) === '1';
    } catch {
      return fallback;
    }
  });
  const setFlag = useCallback(
    (next: boolean) => {
      setValue(next);
      try {
        window.localStorage.setItem(key, next ? '1' : '0');
      } catch {
        /* ignore quota */
      }
    },
    [key],
  );
  return [value, setFlag] as const;
}

export function NetworkModule() {
  return (
    <ReactFlowProvider>
      <NetworkEditor />
    </ReactFlowProvider>
  );
}

/** M23: an open dropdown, menu, popover or dialog owns the keyboard. */
function overlayOpen(): boolean {
  return Boolean(
    document.querySelector(
      '[role="dialog"][data-state="open"], [role="alertdialog"], [role="listbox"], [role="menu"], [data-radix-popper-content-wrapper]',
    ),
  );
}

/** M23: graph keys act on the canvas or with nothing focused, not on a focused button or field. */
function canvasHasFocus(target: HTMLElement | null): boolean {
  if (!target || target === document.body || target === document.documentElement) return true;
  return Boolean(target.closest('.react-flow'));
}

function NetworkEditor() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const versionsOpen = useVersionPreview((state) => state.sheetOpen);
  const setVersionsOpen = useVersionPreview((state) => state.setSheetOpen);
  const preview = useVersionPreview((state) => state.preview);
  const setPreview = useVersionPreview((state) => state.setPreview);
  const clearPreview = useVersionPreview((state) => state.clearPreview);
  const savedRevision = useNetworkEditor((state) => state.saved?.revision ?? 0);
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const { screenToFlowPosition } = useReactFlow();
  const activeNetworkId = useAppStore((state) => state.activeNetworkId);
  const serviceStatus = useAppStore((state) => state.serviceStatus);
  const document = useNetworkEditor((state) => state.document);
  const hydrate = useNetworkEditor((state) => state.hydrate);
  const resetNew = useNetworkEditor((state) => state.resetNew);
  const query = useEditorNetworkQuery(id);
  const loadedRoute = useRef<string | undefined>(undefined);

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [paletteCollapsed, setPaletteCollapsed] = useLocalFlag('agentus.network.paletteCollapsed');
  const [inspectorCollapsed, setInspectorCollapsed] = useLocalFlag('agentus.network.inspectorCollapsed');
  const [inspectorWidth, setInspectorWidth] = useLocalWidth('agentus.network.inspectorWidth', INSPECTOR_MIN);
  const inspectorDrag = useRef({ x: 0, width: INSPECTOR_MIN });
  const inspectorWidthRef = useRef(inspectorWidth);
  inspectorWidthRef.current = inspectorWidth;
  const editorRowRef = useRef<HTMLDivElement>(null);
  const inspectorLimit = useCallback(() => {
    const row = editorRowRef.current;
    if (!row) return inspectorWidthRef.current;
    return Math.max(INSPECTOR_MIN, row.clientWidth - 280);
  }, []);
  useEffect(() => {
    const row = editorRowRef.current;
    if (!row || !isDesktop) return;
    const fit = () => setInspectorWidth(Math.min(inspectorLimit(), inspectorWidthRef.current));
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(row);
    return () => observer.disconnect();
  }, [inspectorLimit, isDesktop, setInspectorWidth]);
  const [loadOpen, setLoadOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [transferBusy, setTransferBusy] = useState(false);
  const library = useEditorNetworksQuery();
  const [nameOpen, setNameOpen] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [nameMode, setNameMode] = useState<'save' | 'saveAs'>('save');
  const [dirtyAction, setDirtyAction] = useState<DirtyAction | null>(null);
  const [saving, setSaving] = useState(false);
  const [versionOpen, setVersionOpen] = useState(false);
  const [versionNote, setVersionNote] = useState('');
  const [savingMode, setSavingMode] = useState<'new' | 'current' | null>(null);
  const [conflict, setConflict] = useState<{ version: number; note?: string } | null>(null);
  const [reloading, setReloading] = useState(false);
  const savedVersion = useNetworkEditor((state) => state.saved?.version);
  const [duplicating, setDuplicating] = useState(false);
  const pendingLoadId = useRef<string | null>(null);
  const pendingActionRef = useRef<DirtyAction | null>(null);
  const allowLeaveRef = useRef(false);
  const leaveToRef = useRef<string | null>(null);
  const clipboard = useRef<ReturnType<typeof duplicateNodes> | null>(null);

  const dirty = useNetworkEditor((state) => state.isDirty());
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const mcp = useMcpServersQuery();
  const mcpRecipes = useMcpRecipesQuery();
  const issues = useMemo(
    () =>
      validateDocument(document, {
        mcpServers: mcp.data?.items,
        mcpRecipes: mcpRecipes.data?.items,
        mcpReady: !mcp.isLoading,
      }),
    [document, mcp.data, mcp.isLoading, mcpRecipes.data],
  );
  const readOnly = Boolean(
    (serviceStatus === 'running' || serviceStatus === 'starting') && document.id && document.id === activeNetworkId,
  );
  const isActive = Boolean(document.id && document.id === activeNetworkId);
  const isRunning = readOnly;
  // A stored version shown read-only instead of the working document (the inspector's picker).
  const previewVersion = preview && document.id && preview.networkId === document.id ? preview.version : null;
  const previewing = previewVersion !== null;
  const versionList = useNetworkVersionsQuery(document.id, previewing);
  useEffect(() => {
    if (previewing) useNetworkEditor.getState().select([]);
  }, [previewing]);

  useEffect(() => {
    if (!id) {
      if (loadedRoute.current !== '') {
        resetNew();
        loadedRoute.current = '';
      }
      return;
    }
    if (query.data && loadedRoute.current !== id) {
      hydrate(query.data, true);
      loadedRoute.current = id;
    }
  }, [hydrate, id, query.data, resetNew]);

  // A version preview and the sheet belong to the open network only.
  useEffect(
    () => () => {
      clearPreview();
      setVersionsOpen(false);
    },
    [id, clearPreview, setVersionsOpen],
  );

  // The Verwaltung links here with ?versions=1 (fix/netz-versionen/entwurf.md, 12).
  useEffect(() => {
    if (!id || searchParams.get('versions') !== '1') return;
    setVersionsOpen(true);
    const next = new URLSearchParams(searchParams);
    next.delete('versions');
    setSearchParams(next, { replace: true });
  }, [id, searchParams, setSearchParams, setVersionsOpen]);

  const shouldBlock = useCallback(
    ({ currentLocation, nextLocation }: { currentLocation: { pathname: string }; nextLocation: { pathname: string; search: string; hash: string } }) => {
      const block =
        !allowLeaveRef.current && dirtyRef.current && currentLocation.pathname !== nextLocation.pathname;
      if (block) leaveToRef.current = `${nextLocation.pathname}${nextLocation.search}${nextLocation.hash}`;
      return block;
    },
    [],
  );
  const blocker = useBlocker(shouldBlock);

  function allowNextNav(fn: () => void) {
    allowLeaveRef.current = true;
    fn();
    queueMicrotask(() => {
      allowLeaveRef.current = false;
    });
  }

  function resolvedAction(): DirtyAction | null {
    return pendingActionRef.current ?? dirtyAction ?? (blocker.state === 'blocked' ? 'leave' : null);
  }

  function runPending(action: DirtyAction | null) {
    pendingActionRef.current = null;
    setDirtyAction(null);
    if (!action) return;
    const blocked = blocker.state === 'blocked';
    const leaveTo = leaveToRef.current;
    allowNextNav(() => {
      if (action === 'leave') {
        if (blocked) blocker.proceed?.();
        else if (leaveTo) navigate(leaveTo);
        leaveToRef.current = null;
        return;
      }
      leaveToRef.current = null;
      if (action === 'new') {
        resetNew();
        navigate('/network');
        return;
      }
      if (action === 'library') {
        navigate('/networks');
        return;
      }
      if (action === 'load' && pendingLoadId.current) {
        const next = pendingLoadId.current;
        pendingLoadId.current = null;
        navigate(`/network/${next}`);
      }
    });
  }

  function revertDirty() {
    const state = useNetworkEditor.getState();
    if (state.saved) state.hydrate(state.saved, true);
    else state.resetNew();
  }

  function cancelDirtyPrompt() {
    pendingActionRef.current = null;
    leaveToRef.current = null;
    setDirtyAction(null);
    if (blocker.state === 'blocked') blocker.reset?.();
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing = Boolean(
        target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.tagName === 'SELECT' ||
            target.isContentEditable),
      );
      const mod = event.metaKey || event.ctrlKey;
      if (mod && event.key.toLowerCase() === 's') {
        event.preventDefault();
        // V-6: Ctrl+S saves straight as a new version; an open save or conflict dialog owns it.
        if (!readOnly && !previewing && !versionOpen && !nameOpen && conflict === null) void save();
        return;
      }
      // The version preview owns the keyboard (arrows step, Esc returns); nothing edits the hidden graph.
      if (previewing) return;
      // M23: inside a text field Ctrl+Z is the field's own undo, not the graph's.
      if (typing) return;
      // M23: dropdowns, menus and dialogs own their keys (arrows, Escape, Delete).
      if (overlayOpen()) return;
      if (mod && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        if (readOnly) return;
        if (event.shiftKey) useNetworkEditor.getState().redo();
        else useNetworkEditor.getState().undo();
        return;
      }
      // Plain keys act on the graph only from the canvas: Delete on a focused button,
      // or arrows on a focused checkbox, must not move or remove the selected node.
      const onCanvas = canvasHasFocus(target);
      if (event.key === 'Escape' && onCanvas) useNetworkEditor.getState().select([]);
      if (mod && event.key.toLowerCase() === 'c') {
        const state = useNetworkEditor.getState();
        clipboard.current = duplicateNodes(state.document.nodes, state.document.edges, state.selectedNodeIds);
      }
      // Selection and copy stay available while the active network runs; edits do not.
      if (readOnly) return;
      if ((event.key === 'Delete' || event.key === 'Backspace') && onCanvas) editorDeleteSelection();
      if (mod && event.key.toLowerCase() === 'd') {
        event.preventDefault();
        editorDuplicateSelection();
      }
      if (mod && event.key.toLowerCase() === 'v' && clipboard.current) {
        const state = useNetworkEditor.getState();
        const pasted = duplicateNodes(clipboard.current.nodes, clipboard.current.edges, clipboard.current.nodes.map((n) => n.id));
        state.applyDocument({
          ...state.document,
          nodes: [...state.document.nodes, ...pasted.nodes],
          edges: [...state.document.edges, ...pasted.edges],
        });
        state.select(pasted.nodes.map((node) => node.id));
      }
      if (!onCanvas) return;
      if (event.key === 'ArrowLeft') editorNudge(-1, 0);
      if (event.key === 'ArrowRight') editorNudge(1, 0);
      if (event.key === 'ArrowUp') editorNudge(0, -1);
      if (event.key === 'ArrowDown') editorNudge(0, 1);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const save = useCallback(async (explicitName?: string, options: SaveOptions = {}): Promise<boolean> => {
    const state = useNetworkEditor.getState();
    const current = state.document;
    const name = (explicitName ?? current.name).trim();
    if (!current.id && !name) {
      setNameMode('save');
      setNameValue(current.name);
      setNameOpen(true);
      return false;
    }
    const newVersion = options.newVersion ?? true;
    const before = state.saved?.version;
    setSaving(true);
    setSavingMode(newVersion ? 'new' : 'current');
    try {
      const payload = { ...current, name: name || current.name };
      // The saved copy holds the server's revision; an undo step must not move it back.
      const saved = current.id
        ? await updateNetwork(current.id, payload, {
            baseRevision: options.force ? undefined : state.saved?.revision,
            newVersion,
            note: options.note,
          })
        : await createNetwork(payload);
      // M24: typing during the request must not be replaced by the server copy.
      useNetworkEditor.getState().markSaved(saved, current);
      notify(
        current.id && saved.version && before && saved.version !== before
          ? { titleKey: 'network.notify.savedVersion', values: { version: String(saved.version) }, variant: 'success' }
          : { titleKey: 'network.notify.saved', variant: 'success' },
      );
      if (!pendingActionRef.current && (!id || id !== saved.id)) {
        allowLeaveRef.current = true;
        navigate(`/network/${saved.id}`, { replace: !id });
        queueMicrotask(() => {
          allowLeaveRef.current = false;
        });
      }
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.messageKey === 'networks.conflict') {
        // Section 8: someone else saved in between; nothing was written, the user decides.
        setVersionOpen(false);
        setConflict({ version: Number(error.details.version) || 0, note: options.note });
        return false;
      }
      notify({
        titleKey: error instanceof ApiError && error.messageKey === 'run.busy' ? 'network.notify.saveBusy' : 'network.notify.saveError',
        variant: 'error',
      });
      return false;
    } finally {
      setSaving(false);
      setSavingMode(null);
    }
  }, [id, navigate]);

  function requestSave() {
    // Section 6: an existing network asks how to save; a new one saves as before.
    if (!useNetworkEditor.getState().document.id) {
      void save();
      return;
    }
    setVersionNote('');
    setVersionOpen(true);
  }

  async function confirmVersion(newVersion: boolean) {
    const ok = await save(undefined, { newVersion, note: versionNote });
    if (ok) setVersionOpen(false);
  }

  function continuePending() {
    const action = pendingActionRef.current;
    if (action) runPending(action);
  }

  async function reloadAfterConflict() {
    const networkId = useNetworkEditor.getState().document.id;
    if (!networkId) return;
    setReloading(true);
    try {
      const fresh = await getNetwork(networkId);
      queryClient.setQueryData(['networks', networkId, 'document'], fresh);
      useNetworkEditor.getState().hydrate(fresh, true);
      setConflict(null);
      notify({ titleKey: 'network.conflict.reloaded', variant: 'success' });
      continuePending();
    } catch {
      notify({ titleKey: 'network.notify.saveError', variant: 'error' });
    } finally {
      setReloading(false);
    }
  }

  async function saveOverConflict() {
    // The other state stays as the version before this one (section 8).
    const ok = await save(undefined, { newVersion: true, note: conflict?.note, force: true });
    if (!ok) return;
    setConflict(null);
    continuePending();
  }

  async function saveAsConfirmed(name: string): Promise<boolean> {
    setSaving(true);
    try {
      const before = useNetworkEditor.getState().document;
      const { id: _id, ...rest } = before;
      void _id;
      const saved = await createNetwork({ ...rest, name });
      useNetworkEditor.getState().markSaved(saved, before);
      notify({ titleKey: 'network.notify.saved', variant: 'success' });
      if (!pendingActionRef.current) {
        allowLeaveRef.current = true;
        navigate(`/network/${saved.id}`);
        queueMicrotask(() => {
          allowLeaveRef.current = false;
        });
      }
      return true;
    } catch {
      notify({ titleKey: 'network.notify.saveError', variant: 'error' });
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function rebuildIndexes(networkId: string, nodes: { id: string; name: string }[]) {
    let failed = 0;
    for (const node of nodes) {
      try {
        const result = await reindexNetworkKnowledge(networkId, node.id);
        if (result.state === 'error') failed += 1;
      } catch {
        failed += 1;
      }
    }
    notify({
      titleKey: failed ? 'network.versions.reindexFailed' : 'network.versions.reindexDone',
      variant: failed ? 'error' : 'success',
    });
  }

  function notifyCopied(copy: AgentNetworkDocument) {
    notify({
      titleKey: 'network.versions.copied',
      values: { name: copy.name },
      variant: 'success',
      toastAction: copy.id ? { labelKey: 'network.versions.open', onClick: () => navigate(`/network/${copy.id}`) } : undefined,
    });
  }

  /** V-3: a restored knowledge node may have lost its index; offer to rebuild it. */
  function afterRestore(restored: AgentNetworkDocument, from: number) {
    clearPreview();
    useNetworkEditor.getState().hydrate(restored, true);
    notify({
      titleKey: 'network.versions.restored',
      values: { from: String(from), version: String(restored.version ?? '') },
      variant: 'success',
    });
    const missing = knowledgeWithoutIndex(restored);
    if (restored.id && missing.length > 0) {
      const networkId = restored.id;
      notify({
        titleKey: 'network.versions.reindexTitle',
        values: { names: missing.map((node) => node.name).join(', ') },
        variant: 'warning',
        duration: 20_000,
        toastAction: { labelKey: 'network.versions.reindex', onClick: () => void rebuildIndexes(networkId, missing) },
      });
    }
  }

  function requestNew() {
    if (dirty) {
      setDirtyAction('new');
      return;
    }
    resetNew();
    navigate('/network');
  }

  function requestLibrary() {
    if (dirty) {
      setDirtyAction('library');
      return;
    }
    navigate('/networks');
  }

  function openLoaded(networkId: string) {
    if (dirty) {
      pendingLoadId.current = networkId;
      setDirtyAction('load');
      setLoadOpen(false);
      return;
    }
    setLoadOpen(false);
    navigate(`/network/${networkId}`);
  }

  function discardAndContinue() {
    const action = resolvedAction();
    revertDirty();
    runPending(action);
  }

  async function saveAndContinue() {
    const action = resolvedAction() ?? 'leave';
    pendingActionRef.current = action;
    const ok = await save();
    if (!ok) return;
    setNameOpen(false);
    runPending(action);
  }

  async function confirmName() {
    const name = nameValue.trim();
    if (!name) return;
    const ok = nameMode === 'saveAs' ? await saveAsConfirmed(name) : await save(name);
    if (!ok) return;
    setNameOpen(false);
    const action = pendingActionRef.current;
    if (action) runPending(action);
  }

  async function duplicate() {
    if (!document.id) return;
    setDuplicating(true);
    try {
      const copy = await duplicateNetwork(document.id);
      notify({ titleKey: 'network.notify.duplicated', variant: 'success' });
      navigate(`/network/${copy.id}`);
    } catch {
      notify({ titleKey: 'network.notify.saveError', variant: 'error' });
    } finally {
      setDuplicating(false);
    }
  }

  async function confirmExport() {
    setTransferBusy(true);
    try {
      const payload = await previewExport(useNetworkEditor.getState().document);
      const name = payload.name || document.name || 'network';
      const written = await saveExportFile(
        `${exportFileStem(name)}-${exportStamp()}.json`,
        new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: 'application/json' }),
      );
      if (!written) return;
      setExportOpen(false);
      notify({ titleKey: 'networks.notify.exported', variant: 'success' });
    } catch {
      notify({ titleKey: 'networks.notify.error', variant: 'error' });
    } finally {
      setTransferBusy(false);
    }
  }

  function confirmImport(documents: AgentNetworkDocument[]) {
    const documentToImport = documents[0];
    if (!documentToImport) return;
    setTransferBusy(true);
    void importNetwork(documentToImport)
      .then((created) => {
        setImportOpen(false);
        notify({
          titleKey: 'networks.notify.imported',
          values: { count: '1' },
          variant: 'success',
        });
        if (created.id) openLoaded(created.id);
      })
      .catch(() => {
        notify({ titleKey: 'networks.notify.error', variant: 'error' });
      })
      .finally(() => {
        setTransferBusy(false);
      });
  }

  async function runValidate() {
    try {
      const result = await validateNetwork(document);
      notify({
        titleKey: result.valid ? 'network.notify.valid' : 'network.notify.invalid',
        variant: result.valid ? 'success' : 'warning',
      });
    } catch {
      notify({ titleKey: 'network.notify.saveError', variant: 'error' });
    }
  }

  function insertPosition() {
    const center = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    try {
      return screenToFlowPosition(center);
    } catch {
      return { x: 120, y: 120 };
    }
  }

  if (id && query.isLoading && !query.data) {
    return <ModuleLoading />;
  }

  if (id && query.isError) {
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertTitle>{t('network.error.missing')}</AlertTitle>
          <AlertDescription>
            <Button asChild size="sm" variant="outline" className="mt-2">
              <Link to="/network">{t('network.ribbon.new')}</Link>
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const palette = <Palette disabled={readOnly || previewing} insertAt={insertPosition} />;
  const inspector = (
    <Inspector issues={issues} readOnly={readOnly || previewing} isActive={isActive} isRunning={isRunning} />
  );

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      {readOnly ? (
        <Alert className="rounded-none border-x-0 border-t-0">
          <AlertTitle>{t('network.readonly.title')}</AlertTitle>
          <AlertDescription>{t('network.readonly.body')}</AlertDescription>
        </Alert>
      ) : null}
      <Ribbon
        dirty={dirty}
        valid={issues.length === 0 && Boolean(document.name.trim())}
        isActive={isActive}
        isRunning={isRunning}
        readOnly={readOnly || previewing}
        saving={saving}
        duplicating={duplicating}
        onNew={requestNew}
        onSave={requestSave}
        onSaveAs={() => {
          setNameMode('saveAs');
          setNameValue(`${document.name} ${t('network.copySuffix')}`.trim());
          setNameOpen(true);
        }}
        onLoad={() => setLoadOpen(true)}
        onDuplicate={() => void duplicate()}
        onImport={() => setImportOpen(true)}
        onExport={() => setExportOpen(true)}
        onValidate={() => void runValidate()}
        onLibrary={requestLibrary}
        onVersions={() => setVersionsOpen(true)}
      />
      {!isDesktop ? (
        <div className="flex gap-2 border-b px-2 py-1">
          <Button type="button" size="sm" variant="outline" onClick={() => setPaletteOpen(true)}>
            {t('network.palette.title')}
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => setInspectorOpen(true)}>
            {t('network.inspector.title')}
          </Button>
        </div>
      ) : null}
      <div ref={editorRowRef} className="flex min-h-0 flex-1">
        {isDesktop ? (
          <aside
            className={cn(
              'hidden shrink-0 flex-col border-r md:flex',
              paletteCollapsed ? 'w-11' : 'w-52',
            )}
          >
            <div className={cn('flex items-center p-1', paletteCollapsed ? 'justify-center' : 'justify-between px-2')}>
              {paletteCollapsed ? null : (
                <span className="truncate text-xs font-medium text-muted-foreground">{t('network.palette.title')}</span>
              )}
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7 shrink-0"
                aria-label={t(paletteCollapsed ? 'network.palette.expand' : 'network.palette.collapse')}
                title={t(paletteCollapsed ? 'network.palette.expand' : 'network.palette.collapse')}
                onClick={() => setPaletteCollapsed(!paletteCollapsed)}
              >
                {paletteCollapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
              </Button>
            </div>
            <div className={cn('min-h-0 flex-1', paletteCollapsed ? 'px-1 pb-2' : 'p-2 pt-0')}>
              <Palette disabled={readOnly || previewing} insertAt={insertPosition} compact={paletteCollapsed} />
            </div>
          </aside>
        ) : null}
        <div className="min-h-0 min-w-0 flex-1">
          {previewVersion !== null && document.id ? (
            <VersionPreview
              networkId={document.id}
              networkName={document.name}
              version={previewVersion}
              versions={versionList.data}
              dirty={dirty}
              running={readOnly}
              onSelect={(version) => setPreview(document.id as string, version)}
              onRestored={afterRestore}
              onCopied={notifyCopied}
            />
          ) : (
            <FlowCanvas
              readOnly={readOnly}
              onRequestInsert={() => setPaletteOpen(true)}
              onOpenInspector={() => {
                setInspectorCollapsed(false);
                if (!isDesktop) setInspectorOpen(true);
              }}
            />
          )}
        </div>
        {isDesktop && !inspectorCollapsed ? (
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label={t('network.inspector.resize')}
            aria-valuenow={inspectorWidth}
            aria-valuemin={INSPECTOR_MIN}
            tabIndex={0}
            className="hidden w-4 shrink-0 cursor-col-resize touch-none items-center justify-center self-stretch rounded-sm hover:bg-muted/50 focus-visible:bg-muted/50 md:flex"
            onPointerDown={(event) => {
              inspectorDrag.current = { x: event.clientX, width: inspectorWidth };
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
              const next = inspectorDrag.current.width - (event.clientX - inspectorDrag.current.x);
              setInspectorWidth(Math.min(inspectorLimit(), next));
            }}
            onKeyDown={(event) => {
              if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
              event.preventDefault();
              const step = event.shiftKey ? 48 : 16;
              const delta = event.key === 'ArrowLeft' ? step : -step;
              setInspectorWidth(Math.min(inspectorLimit(), inspectorWidth + delta));
            }}
          >
            <span className="h-8 w-1 rounded-full bg-border" aria-hidden />
          </div>
        ) : null}
        {isDesktop ? (
          <aside
            className={cn(
              'hidden min-w-0 shrink-0 flex-col md:flex',
              inspectorCollapsed ? 'w-11 border-l' : '',
            )}
            style={inspectorCollapsed ? undefined : { width: inspectorWidth }}
          >
            <div className={cn('flex items-center p-1', inspectorCollapsed ? 'justify-center' : 'justify-between px-2')}>
              {inspectorCollapsed ? null : (
                <span className="truncate text-xs font-medium text-muted-foreground">
                  {t('network.inspector.title')}
                </span>
              )}
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7 shrink-0"
                aria-label={t(inspectorCollapsed ? 'network.inspector.expand' : 'network.inspector.collapse')}
                title={t(inspectorCollapsed ? 'network.inspector.expand' : 'network.inspector.collapse')}
                onClick={() => setInspectorCollapsed(!inspectorCollapsed)}
              >
                {inspectorCollapsed ? <ChevronsLeft className="size-4" /> : <ChevronsRight className="size-4" />}
              </Button>
            </div>
            {inspectorCollapsed ? null : (
              <div className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto">{inspector}</div>
            )}
          </aside>
        ) : null}
      </div>
      <Sheet open={paletteOpen} onOpenChange={setPaletteOpen}>
        <SheetContent side="left" closeLabel={t('network.dialog.close')}>
          <SheetHeader>
            <SheetTitle>{t('network.palette.title')}</SheetTitle>
          </SheetHeader>
          <div className="mt-3 h-[70vh]">{palette}</div>
        </SheetContent>
      </Sheet>
      <Sheet open={inspectorOpen} onOpenChange={setInspectorOpen}>
        <SheetContent side="right" closeLabel={t('network.dialog.close')}>
          <SheetHeader>
            <SheetTitle>{t('network.inspector.title')}</SheetTitle>
          </SheetHeader>
          <div className="mt-3 h-[70vh] overflow-auto">{inspector}</div>
        </SheetContent>
      </Sheet>
      <LoadDialog open={loadOpen} onOpenChange={setLoadOpen} onOpen={openLoaded} />
      <ExportDialog
        open={exportOpen}
        items={[
          {
            name: document.name,
            nodeCount: document.nodes.length,
            edgeCount: document.edges.length,
          },
        ]}
        busy={transferBusy}
        onClose={() => setExportOpen(false)}
        onConfirm={() => void confirmExport()}
      />
      <ImportDialog
        open={importOpen}
        multiple={false}
        existingNames={(library.data?.items ?? []).map((item) => item.name)}
        busy={transferBusy}
        onClose={() => setImportOpen(false)}
        onImport={confirmImport}
      />
      <Dialog open={nameOpen} onOpenChange={setNameOpen}>
        <DialogContent closeLabel={t('network.dialog.close')}>
          <DialogHeader>
            <DialogTitle>
              {nameMode === 'saveAs' ? t('network.ribbon.saveAs') : t('network.dialog.nameTitle')}
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="network-name">{t('network.inspector.graph.name')}</Label>
            <Input
              id="network-name"
              value={nameValue}
              autoFocus
              onChange={(event) => setNameValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  void confirmName();
                }
              }}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setNameOpen(false)}>
              {t('network.dialog.cancel')}
            </Button>
            <Button type="button" disabled={!nameValue.trim()} loading={saving} onClick={() => void confirmName()}>
              {t('network.ribbon.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <VersionsSheet
        open={versionsOpen}
        onOpenChange={setVersionsOpen}
        networkId={document.id}
        networkName={document.name}
        savedRevision={savedRevision}
        dirty={dirty}
        readOnly={readOnly}
        onRestored={(restored, from) => {
          setVersionsOpen(false);
          afterRestore(restored, from);
        }}
        onCopied={notifyCopied}
        onViewInEditor={(version) => {
          setVersionsOpen(false);
          if (document.id) setPreview(document.id, version);
        }}
      />
      <Dialog open={versionOpen} onOpenChange={setVersionOpen}>
        {/* Three buttons side by side need more than the default 32rem. */}
        <DialogContent className="sm:max-w-[38rem]" closeLabel={t('network.dialog.close')}>
          <DialogHeader>
            <DialogTitle>{t('network.save.title', { name: document.name })}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="network-version-note">{t('network.save.note')}</Label>
            <Input
              id="network-version-note"
              value={versionNote}
              autoFocus
              maxLength={200}
              placeholder={t('network.save.notePlaceholder')}
              onChange={(event) => setVersionNote(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  if (!saving) void confirmVersion(true);
                }
              }}
            />
            {savedVersion ? (
              <p className="text-xs text-muted-foreground">
                {t('network.save.overwriteHint', { version: savedVersion })}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setVersionOpen(false)}>
              {t('network.dialog.cancel')}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={saving && savingMode !== 'current'}
              loading={savingMode === 'current'}
              onClick={() => void confirmVersion(false)}
            >
              {t('network.save.sameVersion')}
            </Button>
            <Button
              type="button"
              disabled={saving && savingMode !== 'new'}
              loading={savingMode === 'new'}
              onClick={() => void confirmVersion(true)}
            >
              {t('network.save.newVersion')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <AlertDialog
        open={conflict !== null}
        onOpenChange={(open) => {
          if (!open) setConflict(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('network.conflict.title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('network.conflict.body', { version: conflict?.version ?? '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            <li>{t('network.conflict.reloadHint')}</li>
            <li>{t('network.conflict.saveHint')}</li>
          </ul>
          <AlertDialogFooter>
            <Button type="button" variant="outline" onClick={() => setConflict(null)}>
              {t('network.conflict.cancel')}
            </Button>
            <Button
              type="button"
              variant="outline"
              loading={reloading}
              disabled={saving}
              onClick={() => void reloadAfterConflict()}
            >
              {t('network.conflict.reload')}
            </Button>
            <Button type="button" loading={saving} disabled={reloading} onClick={() => void saveOverConflict()}>
              {t('network.conflict.saveNew')}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog
        open={(dirtyAction !== null || blocker.state === 'blocked') && !nameOpen && conflict === null}
        onOpenChange={(open) => {
          if (!open) cancelDirtyPrompt();
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('network.dirty.title')}</AlertDialogTitle>
            <AlertDialogDescription>{t('network.dirty.body')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button type="button" variant="outline" onClick={cancelDirtyPrompt}>
              {t('network.dirty.cancel')}
            </Button>
            <Button type="button" variant="outline" loading={saving} onClick={() => void saveAndContinue()}>
              {t('network.dirty.save')}
            </Button>
            <Button type="button" onClick={discardAndContinue}>
              {t('network.dirty.discard')}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
