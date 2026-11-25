import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { Eye, Pin, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ApiError, queryClient } from '@/api/client';
import { notify } from '@/lib/notifications';
import { cn } from '@/lib/utils';
import type { AgentNetworkDocument } from '@/modules/network/model/document';
import { diffMarks } from '@/modules/network/model/diff';
import { DiffList } from '@/modules/network/versions/DiffList';
import { useVersionPreview } from '@/modules/network/versions/previewStore';
import { DeleteVersionConfirm, DiscardConfirm, VersionSource } from '@/modules/network/versions/VersionParts';
import { useVersionActions, versionStamp } from '@/modules/network/versions/versionActions';
import {
  deleteNetworkVersion,
  patchNetworkVersion,
  versionKeys,
  useNetworkVersionQuery,
  useNetworkVersionsQuery,
  useVersionDiffQuery,
  type NetworkVersionItem,
} from '@/modules/network/versions/api';
import { DocumentGraph } from '@/modules/networks/detail/ReadonlyGraph';

/**
 * Enter acts on the focused control only. The app's dialogs press their main button on Enter;
 * here that would be "Wiederherstellen" while the user just picks a version from the list.
 */
function enterOnFocused(event: KeyboardEvent<HTMLDivElement>) {
  if (event.key !== 'Enter' || event.defaultPrevented) return;
  event.preventDefault();
  if (event.target instanceof HTMLButtonElement) event.target.click();
}

/** Into the list, on the version shown; not on "Wiederherstellen". False while the list loads. */
function focusList(root: HTMLUListElement | null): boolean {
  const target = root?.querySelector<HTMLButtonElement>('button[aria-current="true"]') ?? root?.querySelector<HTMLButtonElement>('button');
  target?.focus();
  return Boolean(target);
}

/**
 * The versions of the open network (fix/netz-versionen/entwurf.md, 12) as a dialog over the
 * editor: list, pin, note, preview with the difference to the current state, restore, copy as a
 * new network, view in the editor.
 */
export function VersionsDialog({
  open,
  onOpenChange,
  networkId,
  networkName,
  savedRevision,
  dirty,
  readOnly,
  onRestored,
  onCopied,
  onViewInEditor,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  networkId: string | undefined;
  networkName: string;
  savedRevision: number;
  dirty: boolean;
  readOnly: boolean;
  onRestored: (document: AgentNetworkDocument, from: number) => void;
  onCopied: (document: AgentNetworkDocument) => void;
  /** Show a version read-only in the editor's canvas. */
  onViewInEditor: (version: number) => void;
}) {
  const { t, i18n } = useTranslation();
  const list = useNetworkVersionsQuery(networkId, open);
  const current = list.data?.version ?? null;
  const [selected, setSelected] = useState<number | null>(null);
  const [note, setNote] = useState('');
  const [pinning, setPinning] = useState(false);
  const [confirm, setConfirm] = useState(false);
  /** The version whose deletion is being asked about. */
  const [deleting, setDeleting] = useState<number | null>(null);
  const [removing, setRemoving] = useState(false);
  const actions = useVersionActions({ networkId, networkName, onRestored, onCopied });
  const preview = useVersionPreview((state) => state.preview);
  const clearPreview = useVersionPreview((state) => state.clearPreview);
  const listRef = useRef<HTMLUListElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    setSelected(null);
    setConfirm(false);
    setDeleting(null);
  }, [open, networkId]);

  const items = useMemo(() => list.data?.items ?? [], [list.data]);

  // Opened before the list arrived: the dialog itself held focus; move it once the entries are there.
  useEffect(() => {
    if (open && items.length > 0 && document.activeElement === contentRef.current) focusList(listRef.current);
  }, [open, items.length]);
  const shown = selected ?? current;
  const item = items.find((entry) => entry.version === shown) ?? null;
  const version = useNetworkVersionQuery(networkId, shown);
  const compare = useVersionDiffQuery(networkId, shown !== current ? shown : null, list.data?.revision ?? savedRevision);
  const diff = shown !== current ? compare.data?.diff ?? null : null;
  const marks = useMemo(() => diffMarks(diff), [diff]);

  useEffect(() => setNote(item?.note ?? ''), [item?.version, item?.note]);

  async function togglePin(entry: NetworkVersionItem) {
    if (!networkId) return;
    setPinning(true);
    try {
      await patchNetworkVersion(networkId, entry.version, { pinned: !entry.pinned });
    } catch {
      notify({ titleKey: 'network.versions.error', variant: 'error' });
    } finally {
      setPinning(false);
    }
  }

  async function saveNote() {
    if (!networkId || !item || note.trim() === (item.note ?? '')) return;
    try {
      await patchNetworkVersion(networkId, item.version, { note: note.trim() });
    } catch {
      notify({ titleKey: 'network.versions.error', variant: 'error' });
    }
  }

  async function restore() {
    setConfirm(false);
    if (shown !== null && (await actions.restore(shown, list.data?.revision ?? savedRevision))) setSelected(null);
  }

  async function remove() {
    const version = deleting;
    if (!networkId || version === null) return;
    setRemoving(true);
    try {
      await deleteNetworkVersion(networkId, version);
      if (selected === version) setSelected(null);
      // The editor must not keep previewing a version that is gone.
      if (preview?.networkId === networkId && preview.version === version) clearPreview();
      notify({ titleKey: 'network.versions.deleted', values: { version: String(version) }, variant: 'success' });
    } catch (caught) {
      const key = caught instanceof ApiError ? caught.messageKey : undefined;
      notify({
        titleKey:
          key === 'networks.versionPinned'
            ? 'network.versions.deletePinned'
            : key === 'networks.versionCurrent'
              ? 'network.versions.deleteCurrent'
              : 'network.versions.error',
        variant: 'error',
      });
      // Pinned or saved elsewhere meanwhile: show what is true now.
      void queryClient.invalidateQueries({ queryKey: versionKeys.list(networkId), exact: true });
    } finally {
      setRemoving(false);
      setDeleting(null);
    }
  }

  const busy = actions.busy !== null || pinning || removing;
  const isCurrent = shown === current;

  return (
    <Dialog open={open} onOpenChange={(next) => (actions.busy || removing ? undefined : onOpenChange(next))}>
      <DialogContent
        ref={contentRef}
        className="flex h-[min(90vh,52rem)] flex-col gap-4 sm:max-w-5xl"
        closeLabel={t('network.dialog.close')}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          if (!focusList(listRef.current)) contentRef.current?.focus();
        }}
        onKeyDown={enterOnFocused}
      >
        <DialogHeader className="pe-8">
          <DialogTitle>{t('network.versions.title', { name: networkName })}</DialogTitle>
          <DialogDescription>{t('network.versions.lead')}</DialogDescription>
        </DialogHeader>
        {list.isError ? <p className="text-sm text-destructive">{t('network.versions.error')}</p> : null}
        <div className="grid min-h-0 flex-1 gap-4 overflow-y-auto md:grid-cols-[19rem_minmax(0,1fr)] md:overflow-hidden">
          <ul
            ref={listRef}
            className="max-h-56 overflow-y-auto rounded-md border md:max-h-none md:min-h-0"
            aria-label={t('network.versions.list')}
          >
            {list.isLoading ? <li className="p-3 text-sm text-muted-foreground">{t('network.versions.loading')}</li> : null}
            {items.map((entry) => (
              <li key={entry.version} className="border-b last:border-b-0">
                <div className={cn('flex items-start gap-1 pe-1.5', entry.version === shown && 'bg-primary/10')}>
                  <button
                    type="button"
                    className="min-w-0 flex-1 rounded-sm px-2 py-1.5 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                    aria-current={entry.version === shown ? 'true' : undefined}
                    onClick={() => setSelected(entry.version)}
                  >
                    <span className="flex flex-wrap items-center gap-1.5">
                      <span className="font-medium">{t('network.versions.version', { version: entry.version })}</span>
                      {entry.version === current ? <Badge className="px-1.5 py-0 text-[10px]">{t('network.versions.current')}</Badge> : null}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {versionStamp(entry.updatedAt, i18n.language)} · <VersionSource item={entry} />
                    </span>
                    {entry.note ? <span className="block truncate text-xs">{entry.note}</span> : null}
                  </button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className={cn('mt-1 size-7 shrink-0', entry.pinned ? 'text-primary' : 'text-muted-foreground')}
                    disabled={busy}
                    aria-pressed={entry.pinned}
                    aria-label={entry.pinned ? t('network.versions.unpin') : t('network.versions.pin')}
                    title={entry.pinned ? t('network.versions.unpin') : t('network.versions.pin')}
                    onClick={() => void togglePin(entry)}
                  >
                    <Pin className={cn('size-3.5', entry.pinned && 'fill-current')} />
                  </Button>
                  {entry.version === current ? (
                    // The current version is the network itself; it keeps the column aligned instead.
                    <span className="mt-1 size-7 shrink-0" aria-hidden />
                  ) : (
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="mt-1 size-7 shrink-0 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      disabled={busy || entry.pinned}
                      aria-label={t('network.versions.delete', { version: entry.version })}
                      title={entry.pinned ? t('network.versions.deletePinned') : t('network.versions.delete', { version: entry.version })}
                      onClick={() => setDeleting(entry.version)}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <section className="flex min-h-0 flex-col gap-4" aria-label={item ? t('network.versions.version', { version: item.version }) : undefined}>
            {item ? (
              <>
                <div className="grid gap-1.5 text-sm">
                  <h3 className="flex flex-wrap items-baseline gap-x-2 font-medium">
                    {t('network.versions.version', { version: item.version })}
                    <span className="text-xs font-normal text-muted-foreground">
                      {versionStamp(item.createdAt, i18n.language)} · <VersionSource item={item} /> · {t('network.versions.nodes', { count: item.nodeCount })}
                    </span>
                  </h3>
                  <Input
                    value={note}
                    maxLength={200}
                    placeholder={t('network.versions.notePlaceholder')}
                    aria-label={t('network.versions.note')}
                    onChange={(event) => setNote(event.target.value)}
                    onBlur={() => void saveNote()}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        void saveNote();
                      }
                    }}
                  />
                </div>
                <div className="min-h-64 flex-1 overflow-hidden rounded-md border">
                  {version.data ? (
                    <DocumentGraph document={version.data.document} marks={marks} />
                  ) : (
                    <p className="p-3 text-sm text-muted-foreground">{t('network.versions.loading')}</p>
                  )}
                </div>
                <div className="grid max-h-40 shrink-0 gap-1.5 overflow-y-auto text-sm">
                  <h3 className="font-medium">{t('network.versions.compare')}</h3>
                  {isCurrent ? (
                    <p className="text-xs text-muted-foreground">{t('network.versions.isCurrent')}</p>
                  ) : diff ? (
                    <DiffList diff={diff} />
                  ) : (
                    <p className="text-xs text-muted-foreground">{t('network.versions.loading')}</p>
                  )}
                </div>
              </>
            ) : list.data && items.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t('network.versions.empty')}</p>
            ) : null}
          </section>
        </div>
        <DialogFooter className="sm:flex-wrap">
          <Button type="button" variant="outline" disabled={actions.busy !== null} onClick={() => onOpenChange(false)}>
            {t('network.dialog.close')}
          </Button>
          {item && !isCurrent ? (
            <Button type="button" variant="outline" disabled={busy} onClick={() => onViewInEditor(item.version)}>
              <Eye className="size-4" aria-hidden />
              {t('network.versions.viewInEditor')}
            </Button>
          ) : null}
          {item ? (
            <Button type="button" variant="outline" loading={actions.busy === 'copy'} disabled={busy} onClick={() => void actions.copy(item.version)}>
              {t('network.versions.copy')}
            </Button>
          ) : null}
          {item ? (
            <Button
              type="button"
              data-dialog-primary
              loading={actions.busy === 'restore'}
              disabled={busy || isCurrent || readOnly}
              title={readOnly ? t('network.versions.busy') : undefined}
              onClick={() => (dirty ? setConfirm(true) : void restore())}
            >
              {t('network.versions.restore')}
            </Button>
          ) : null}
        </DialogFooter>
        <DiscardConfirm open={confirm} onCancel={() => setConfirm(false)} onConfirm={() => void restore()} />
        <DeleteVersionConfirm version={deleting} busy={removing} onCancel={() => setDeleting(null)} onConfirm={() => void remove()} />
      </DialogContent>
    </Dialog>
  );
}
