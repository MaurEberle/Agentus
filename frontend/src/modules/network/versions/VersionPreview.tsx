import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Eye, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { AgentNetworkDocument } from '@/modules/network/model/document';
import { diffMarks } from '@/modules/network/model/diff';
import { DiffList } from '@/modules/network/versions/DiffList';
import { DiscardConfirm, VersionSource } from '@/modules/network/versions/VersionParts';
import { useVersionActions, versionStamp } from '@/modules/network/versions/versionActions';
import { useNetworkVersionQuery, useVersionDiffQuery, type NetworkVersionList } from '@/modules/network/versions/api';
import { DocumentGraph } from '@/modules/networks/detail/ReadonlyGraph';

function typing(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  return Boolean(
    element && (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA' || element.tagName === 'SELECT' || element.isContentEditable),
  );
}

function overlayOpen(): boolean {
  return Boolean(document.querySelector('[role="dialog"][data-state="open"], [role="alertdialog"], [data-radix-popper-content-wrapper]'));
}

/**
 * A stored version in place of the canvas, read-only (fix/netz-versionen/entwurf.md, 12).
 * Marks show what restoring it would change on the current version; the working document,
 * unsaved changes included, stays untouched until the user restores.
 */
export function VersionPreview({
  networkId,
  networkName,
  version,
  versions,
  dirty,
  running,
  onSelect,
  onRestored,
  onCopied,
}: {
  networkId: string;
  networkName: string;
  version: number;
  versions: NetworkVersionList | undefined;
  dirty: boolean;
  running: boolean;
  /** ``null`` returns to the current version. */
  onSelect: (version: number | null) => void;
  onRestored: (document: AgentNetworkDocument, from: number) => void;
  onCopied: (document: AgentNetworkDocument) => void;
}) {
  const { t, i18n } = useTranslation();
  const stored = useNetworkVersionQuery(networkId, version);
  const compare = useVersionDiffQuery(networkId, version, versions?.revision ?? 0);
  const diff = compare.data?.diff ?? null;
  const marks = useMemo(() => diffMarks(diff), [diff]);
  const actions = useVersionActions({ networkId, networkName, onRestored, onCopied });
  const [confirm, setConfirm] = useState(false);

  const items = versions?.items ?? [];
  const index = items.findIndex((item) => item.version === version);
  const item = index >= 0 ? items[index] : null;
  const older = index >= 0 ? items[index + 1] ?? null : null;
  const newer = index > 0 ? items[index - 1] : null;
  const current = versions?.version ?? null;
  const step = (target: typeof newer) => onSelect(!target || target.version === current ? null : target.version);

  // ← older, → newer, Esc back to the current version.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (typing(event.target) || overlayOpen() || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === 'Escape') onSelect(null);
      else if (event.key === 'ArrowLeft' && older) step(older);
      else if (event.key === 'ArrowRight') step(newer);
      else return;
      event.preventDefault();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  async function restore() {
    setConfirm(false);
    await actions.restore(version, versions?.revision);
  }

  const changes = diff ? diff.added.length + diff.changed.length + diff.removed.length + (diff.head.length ? 1 : 0) : null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        className="grid gap-2 border-b bg-warning/10 px-3 py-2 text-sm"
        role="region"
        aria-label={t('network.versions.preview.title', { version })}
      >
        {/* Row 1: which version, read-only, when and from where. */}
        <div className="flex min-w-0 items-center gap-2">
          <Eye className="size-4 shrink-0 text-warning" aria-hidden />
          <p className="min-w-0 truncate">
            <span className="font-medium">{t('network.versions.preview.title', { version })}</span>
            <span className="text-muted-foreground">
              {' · '}
              {t('network.versions.preview.readonly')}
              {item ? (
                <>
                  {' · '}
                  {versionStamp(item.updatedAt, i18n.language)} · <VersionSource item={item} />
                  {item.note ? ` · ${item.note}` : ''}
                </>
              ) : null}
            </span>
          </p>
        </div>
        {/* Row 2: step through versions, see the differences, act. */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="size-8"
            disabled={!older}
            aria-label={t('network.versions.preview.older')}
            title={t('network.versions.preview.older')}
            onClick={() => step(older)}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="size-8"
            aria-label={t('network.versions.preview.newer')}
            title={t('network.versions.preview.newer')}
            onClick={() => step(newer)}
          >
            <ChevronRight className="size-4" />
          </Button>
          <Popover>
            <PopoverTrigger asChild>
              <Button type="button" size="sm" variant="ghost" disabled={!diff}>
                {changes === null
                  ? t('network.versions.loading')
                  : changes === 0
                    ? t('network.versions.preview.same')
                    : t('network.versions.preview.changes', { count: changes })}
              </Button>
            </PopoverTrigger>
            {diff ? (
              <PopoverContent align="start" className="w-80 p-3">
                <p className="mb-2 text-xs font-medium">{t('network.versions.compare')}</p>
                <DiffList diff={diff} />
              </PopoverContent>
            ) : null}
          </Popover>
          <span className="flex-1" aria-hidden />
          <Button type="button" size="sm" variant="outline" loading={actions.busy === 'copy'} disabled={actions.busy !== null} onClick={() => void actions.copy(version)}>
            {t('network.versions.copy')}
          </Button>
          <Button
            type="button"
            size="sm"
            loading={actions.busy === 'restore'}
            disabled={actions.busy !== null || running}
            title={running ? t('network.versions.busy') : undefined}
            onClick={() => (dirty ? setConfirm(true) : void restore())}
          >
            {t('network.versions.restore')}
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => onSelect(null)}>
            <X className="size-3.5" aria-hidden />
            {t('network.versions.preview.exit')}
          </Button>
        </div>
        {dirty ? <p className="basis-full text-xs text-muted-foreground">{t('network.versions.preview.unsaved')}</p> : null}
      </div>
      <div className="min-h-0 flex-1">
        {stored.data ? (
          <DocumentGraph document={stored.data.document} marks={marks} />
        ) : (
          <p className="p-4 text-sm text-muted-foreground">
            {stored.isError ? t('network.versions.error') : t('network.versions.loading')}
          </p>
        )}
      </div>
      <DiscardConfirm open={confirm} onCancel={() => setConfirm(false)} onConfirm={() => void restore()} />
    </div>
  );
}
