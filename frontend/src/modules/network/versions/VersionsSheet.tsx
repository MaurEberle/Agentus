import { useEffect, useMemo, useState } from 'react';
import { Eye, Pin } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { notify } from '@/lib/notifications';
import { cn } from '@/lib/utils';
import type { AgentNetworkDocument } from '@/modules/network/model/document';
import { diffMarks } from '@/modules/network/model/diff';
import { DiffList } from '@/modules/network/versions/DiffList';
import { DiscardConfirm, VersionSource } from '@/modules/network/versions/VersionParts';
import { useVersionActions, versionStamp } from '@/modules/network/versions/versionActions';
import {
  patchNetworkVersion,
  useNetworkVersionQuery,
  useNetworkVersionsQuery,
  useVersionDiffQuery,
  type NetworkVersionItem,
} from '@/modules/network/versions/api';
import { DocumentGraph } from '@/modules/networks/detail/ReadonlyGraph';

/**
 * The versions of the open network (fix/netz-versionen/entwurf.md, 12): list, pin, note, preview
 * with the difference to the current state, restore, copy as a new network, view in the editor.
 */
export function VersionsSheet({
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
  const actions = useVersionActions({ networkId, networkName, onRestored, onCopied });

  useEffect(() => {
    if (!open) return;
    setSelected(null);
    setConfirm(false);
  }, [open, networkId]);

  const items = useMemo(() => list.data?.items ?? [], [list.data]);
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

  const busy = actions.busy !== null || pinning;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col gap-3 sm:max-w-4xl" closeLabel={t('network.dialog.close')}>
        <SheetHeader className="pe-8">
          <SheetTitle>{t('network.versions.title', { name: networkName })}</SheetTitle>
          <SheetDescription>{t('network.versions.lead')}</SheetDescription>
        </SheetHeader>
        {list.isError ? <p className="text-sm text-destructive">{t('network.versions.error')}</p> : null}
        <div className="grid min-h-0 flex-1 gap-3 md:grid-cols-[17rem_minmax(0,1fr)]">
          <ul className="min-h-0 overflow-y-auto rounded-md border" aria-label={t('network.versions.list')}>
            {list.isLoading ? <li className="p-3 text-sm text-muted-foreground">{t('network.versions.loading')}</li> : null}
            {items.map((entry) => (
              <li key={entry.version} className="border-b last:border-b-0">
                <div className={cn('flex items-start gap-1 px-2 py-1.5', entry.version === shown && 'bg-primary/10')}>
                  <button
                    type="button"
                    className="min-w-0 flex-1 rounded-sm text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
                    className={cn('size-7 shrink-0', entry.pinned ? 'text-primary' : 'text-muted-foreground')}
                    disabled={busy}
                    aria-pressed={entry.pinned}
                    aria-label={entry.pinned ? t('network.versions.unpin') : t('network.versions.pin')}
                    title={entry.pinned ? t('network.versions.unpin') : t('network.versions.pin')}
                    onClick={() => void togglePin(entry)}
                  >
                    <Pin className={cn('size-3.5', entry.pinned && 'fill-current')} />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
          <section className="flex min-h-0 flex-col gap-2">
            {item ? (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold">{t('network.versions.version', { version: item.version })}</h3>
                  <span className="text-xs text-muted-foreground">
                    {versionStamp(item.createdAt, i18n.language)} · <VersionSource item={item} /> · {t('network.versions.nodes', { count: item.nodeCount })}
                  </span>
                </div>
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
                <div className="min-h-64 flex-1 overflow-hidden rounded-md border">
                  {version.data ? (
                    <DocumentGraph document={version.data.document} marks={marks} />
                  ) : (
                    <p className="p-3 text-sm text-muted-foreground">{t('network.versions.loading')}</p>
                  )}
                </div>
                <div className="grid gap-1">
                  <h4 className="text-xs font-medium">{t('network.versions.compare')}</h4>
                  {shown === current ? (
                    <p className="text-xs text-muted-foreground">{t('network.versions.isCurrent')}</p>
                  ) : diff ? (
                    <DiffList diff={diff} />
                  ) : (
                    <p className="text-xs text-muted-foreground">{t('network.versions.loading')}</p>
                  )}
                </div>
                <div className="flex flex-wrap justify-end gap-2">
                  {shown !== current ? (
                    <Button type="button" variant="ghost" disabled={busy} onClick={() => onViewInEditor(item.version)}>
                      <Eye className="size-4" aria-hidden />
                      {t('network.versions.viewInEditor')}
                    </Button>
                  ) : null}
                  <Button type="button" variant="outline" loading={actions.busy === 'copy'} disabled={busy} onClick={() => void actions.copy(item.version)}>
                    {t('network.versions.copy')}
                  </Button>
                  <Button
                    type="button"
                    loading={actions.busy === 'restore'}
                    disabled={busy || shown === current || readOnly}
                    title={readOnly ? t('network.versions.busy') : undefined}
                    onClick={() => (dirty ? setConfirm(true) : void restore())}
                  >
                    {t('network.versions.restore')}
                  </Button>
                </div>
              </>
            ) : list.data && items.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t('network.versions.empty')}</p>
            ) : null}
          </section>
        </div>
        <DiscardConfirm open={confirm} onCancel={() => setConfirm(false)} onConfirm={() => void restore()} />
      </SheetContent>
    </Sheet>
  );
}
