import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ReactFlowProvider, useReactFlow } from '@xyflow/react';
import { Link, useBlocker, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
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
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { notify } from '@/lib/notifications';
import { useAppStore } from '@/store';
import {
  createNetwork,
  duplicateNetwork,
  updateNetwork,
  useEditorNetworkQuery,
  validateNetwork,
} from '@/modules/network/api';
import { FlowCanvas } from '@/modules/network/canvas/FlowCanvas';
import { Inspector } from '@/modules/network/inspector/Inspector';
import { LoadDialog } from '@/modules/network/library/LoadDialog';
import { downloadJson, duplicateNodes, exportDocument } from '@/modules/network/model/serialize';
import { emptyDocument } from '@/modules/network/model/document';
import { Palette } from '@/modules/network/palette/Palette';
import { Ribbon } from '@/modules/network/ribbon/Ribbon';
import { validateDocument } from '@/modules/network/validation/validate';
import {
  editorDeleteSelection,
  editorDuplicateSelection,
  editorNudge,
  useNetworkEditor,
} from '@/modules/network/store';

type DirtyAction = 'new' | 'load' | 'library' | 'leave';

export function NetworkModule() {
  return (
    <ReactFlowProvider>
      <NetworkEditor />
    </ReactFlowProvider>
  );
}

function NetworkEditor() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
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
  const [loadOpen, setLoadOpen] = useState(false);
  const [nameOpen, setNameOpen] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [nameMode, setNameMode] = useState<'save' | 'saveAs'>('save');
  const [dirtyAction, setDirtyAction] = useState<DirtyAction | null>(null);
  const pendingLoadId = useRef<string | null>(null);
  const clipboard = useRef<ReturnType<typeof duplicateNodes> | null>(null);

  const dirty = useNetworkEditor((state) => state.isDirty());
  const issues = useMemo(() => validateDocument(document), [document]);
  const readOnly = Boolean(
    (serviceStatus === 'running' || serviceStatus === 'starting') && document.id && document.id === activeNetworkId,
  );
  const isActive = Boolean(document.id && document.id === activeNetworkId);
  const isRunning = readOnly;

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

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing =
        target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
      const mod = event.metaKey || event.ctrlKey;
      if (mod && event.key.toLowerCase() === 's') {
        event.preventDefault();
        if (!readOnly) void save();
        return;
      }
      if (mod && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        if (event.shiftKey) useNetworkEditor.getState().redo();
        else useNetworkEditor.getState().undo();
        return;
      }
      if (typing) return;
      if (event.key === 'Escape') useNetworkEditor.getState().select([]);
      if (event.key === 'Delete' || event.key === 'Backspace') editorDeleteSelection();
      if (mod && event.key.toLowerCase() === 'd') {
        event.preventDefault();
        editorDuplicateSelection();
      }
      if (mod && event.key.toLowerCase() === 'c') {
        const state = useNetworkEditor.getState();
        clipboard.current = duplicateNodes(state.document.nodes, state.document.edges, state.selectedNodeIds);
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
      if (event.key === 'ArrowLeft') editorNudge(-1, 0);
      if (event.key === 'ArrowRight') editorNudge(1, 0);
      if (event.key === 'ArrowUp') editorNudge(0, -1);
      if (event.key === 'ArrowDown') editorNudge(0, 1);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const save = useCallback(async (explicitName?: string) => {
    const current = useNetworkEditor.getState().document;
    const name = (explicitName ?? current.name).trim();
    if (!current.id && !name) {
      setNameMode('save');
      setNameValue(current.name);
      setNameOpen(true);
      return;
    }
    try {
      const payload = { ...current, name: name || current.name };
      const saved = current.id
        ? await updateNetwork(current.id, payload)
        : await createNetwork(payload);
      useNetworkEditor.getState().markSaved(saved);
      notify({ titleKey: 'network.notify.saved', variant: 'success' });
      if (!id || id !== saved.id) navigate(`/network/${saved.id}`, { replace: !id });
    } catch {
      notify({ titleKey: 'network.notify.saveError', variant: 'error' });
    }
  }, [id, navigate]);

  async function saveAsConfirmed(name: string) {
    try {
      const { id: _id, ...rest } = useNetworkEditor.getState().document;
      void _id;
      const saved = await createNetwork({ ...rest, name });
      useNetworkEditor.getState().markSaved(saved);
      notify({ titleKey: 'network.notify.saved', variant: 'success' });
      navigate(`/network/${saved.id}`);
    } catch {
      notify({ titleKey: 'network.notify.saveError', variant: 'error' });
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
    const action = dirtyAction;
    setDirtyAction(null);
    if (blocker.state === 'blocked' && action === 'leave') {
      blocker.proceed?.();
      return;
    }
    useNetworkEditor.getState().hydrate(emptyDocument(), false);
    if (action === 'new') {
      resetNew();
      navigate('/network');
    }
    if (action === 'library') navigate('/networks');
    if (action === 'load' && pendingLoadId.current) {
      const next = pendingLoadId.current;
      pendingLoadId.current = null;
      navigate(`/network/${next}`);
    }
  }

  async function duplicate() {
    if (!document.id) return;
    try {
      const copy = await duplicateNetwork(document.id);
      notify({ titleKey: 'network.notify.duplicated', variant: 'success' });
      navigate(`/network/${copy.id}`);
    } catch {
      notify({ titleKey: 'network.notify.saveError', variant: 'error' });
    }
  }

  function exportOpen() {
    const payload = exportDocument(document);
    const filename = `${(document.name || 'network').replace(/[^\w-]+/g, '_')}.json`;
    downloadJson(filename, payload);
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

  const palette = <Palette disabled={readOnly} insertAt={insertPosition} />;
  const inspector = (
    <Inspector issues={issues} readOnly={readOnly} isActive={isActive} isRunning={isRunning} />
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
        readOnly={readOnly}
        onNew={requestNew}
        onSave={() => void save()}
        onSaveAs={() => {
          setNameMode('saveAs');
          setNameValue(`${document.name} ${t('network.copySuffix')}`.trim());
          setNameOpen(true);
        }}
        onLoad={() => setLoadOpen(true)}
        onDuplicate={() => void duplicate()}
        onExport={exportOpen}
        onValidate={() => void runValidate()}
        onLibrary={requestLibrary}
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
      <div className="flex min-h-0 flex-1">
        {isDesktop ? (
          <aside className="hidden w-52 shrink-0 border-r p-2 md:block">{palette}</aside>
        ) : null}
        <div className="min-h-0 min-w-0 flex-1">
          <FlowCanvas readOnly={readOnly} onRequestInsert={() => setPaletteOpen(true)} />
        </div>
        {isDesktop ? (
          <aside className="hidden w-80 shrink-0 overflow-auto border-l md:block">{inspector}</aside>
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
      <Dialog open={nameOpen} onOpenChange={setNameOpen}>
        <DialogContent closeLabel={t('network.dialog.close')}>
          <DialogHeader>
            <DialogTitle>
              {nameMode === 'saveAs' ? t('network.ribbon.saveAs') : t('network.dialog.nameTitle')}
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="network-name">{t('network.inspector.graph.name')}</Label>
            <Input id="network-name" value={nameValue} onChange={(event) => setNameValue(event.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setNameOpen(false)}>
              {t('network.dialog.cancel')}
            </Button>
            <Button
              type="button"
              disabled={!nameValue.trim()}
              onClick={() => {
                const name = nameValue.trim();
                setNameOpen(false);
                if (nameMode === 'saveAs') void saveAsConfirmed(name);
                else void save(name);
              }}
            >
              {t('network.ribbon.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <AlertDialog open={dirtyAction !== null || blocker.state === 'blocked'}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('network.dirty.title')}</AlertDialogTitle>
            <AlertDialogDescription>{t('network.dirty.body')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setDirtyAction(null);
                blocker.reset?.();
              }}
            >
              {t('network.dirty.cancel')}
            </AlertDialogCancel>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                const action = dirtyAction ?? 'leave';
                setDirtyAction(null);
                void save().then(() => {
                  if (action === 'new') {
                    resetNew();
                    navigate('/network');
                  }
                  if (action === 'library') navigate('/networks');
                  if (action === 'load' && pendingLoadId.current) {
                    navigate(`/network/${pendingLoadId.current}`);
                    pendingLoadId.current = null;
                  }
                  if (action === 'leave') blocker.proceed?.();
                });
              }}
            >
              {t('network.dirty.save')}
            </Button>
            <AlertDialogAction onClick={discardAndContinue}>{t('network.dirty.discard')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
