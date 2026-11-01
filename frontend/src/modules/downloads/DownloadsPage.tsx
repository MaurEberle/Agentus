import { useState } from 'react';
import { Pause, Play } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { formatBytes } from '@/lib/format';
import {
  listDownloads,
  pauseDownload,
  pauseDownloads,
  removeDownloads,
  resumeDownload,
  resumeDownloads,
  stopDownload,
} from '@/modules/models/api';
import type { DownloadJob } from '@/modules/models/model';

export function DownloadsPage() {
  const { t, i18n } = useTranslation();
  const [selected, setSelected] = useState<string[]>([]);
  const [pending, setPending] = useState<string[]>([]);
  const [removing, setRemoving] = useState(false);
  const downloads = useQuery({
    queryKey: ['models', 'downloads'],
    queryFn: listDownloads,
    refetchInterval: 1500,
  });
  const items = downloads.data?.items ?? [];
  const paused = Boolean(downloads.data?.paused);
  const canPause = !paused && items.some((item) => item.status === 'queued' || item.status === 'running');
  const canResume = !canPause && (paused || items.some((item) => item.status === 'paused'));
  const selectable = items.filter((item) => item.status !== 'running').map((item) => item.id);
  const allSelected = selectable.length > 0 && selectable.every((id) => selected.includes(id));

  function toggle(id: string) {
    setSelected((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  function toggleAll() {
    setSelected(allSelected ? [] : selectable);
  }

  function askRemove(ids: string[]) {
    if (ids.length === 0 || removing) return;
    setPending(ids);
  }

  async function confirmRemove() {
    const ids = pending;
    if (ids.length === 0) return;
    setRemoving(true);
    try {
      await removeDownloads(ids);
      setSelected((current) => current.filter((id) => !ids.includes(id)));
      setPending([]);
    } finally {
      setRemoving(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
        <Button type="button" size="sm" variant="outline" aria-label={t('models.downloads.pauseAll')} disabled={!canPause} onClick={() => void pauseDownloads()}>
          <Pause className="size-4" />
          {t('models.downloads.pause')}
        </Button>
        <Button type="button" size="sm" variant="outline" aria-label={t('models.downloads.resumeAll')} disabled={!canResume} onClick={() => void resumeDownloads()}>
          <Play className="size-4" />
          {t('models.downloads.resume')}
        </Button>
        <span className="mx-1 h-6 w-px shrink-0 bg-border" aria-hidden />
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={selected.length === 0}
          onClick={() => askRemove(selected)}
        >
          {selected.length > 0 ? t('models.downloads.removeMany', { count: selected.length }) : t('models.downloads.remove')}
        </Button>
      </div>
      {items.length === 0 ? <p className="p-4 text-sm text-muted-foreground">{t('models.downloads.empty')}</p> : (
        <ul className="min-h-0 flex-1 overflow-auto">
          <li className="flex items-center border-b py-2">
            <div className="px-3">
              <Checkbox
                checked={allSelected ? true : selected.length > 0 ? 'indeterminate' : false}
                onCheckedChange={toggleAll}
                aria-label={t('models.list.selectAll')}
                disabled={selectable.length === 0}
              />
            </div>
            <span className="text-sm text-muted-foreground">{t('models.list.selectAll')}</span>
          </li>
          {items.map((item) => (
            <DownloadRow
              key={item.id}
              item={item}
              locale={i18n.language}
              selected={selected.includes(item.id)}
              onToggle={() => toggle(item.id)}
              onRemove={() => askRemove([item.id])}
            />
          ))}
        </ul>
      )}
      <Dialog open={pending.length > 0} onOpenChange={(next) => !next && !removing && setPending([])}>
        <DialogContent closeLabel={t('models.dialog.close')}>
          <DialogHeader>
            <DialogTitle>{t('models.downloads.confirmTitle')}</DialogTitle>
            <DialogDescription>
              {pending.length === 1
                ? t('models.downloads.confirmBody', {
                    name: items.find((item) => item.id === pending[0])?.label ?? '',
                  })
                : t('models.downloads.confirmBodyMany', { count: pending.length })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={removing} onClick={() => setPending([])}>
              {t('models.dialog.cancel')}
            </Button>
            <Button type="button" variant="destructive" disabled={removing} loading={removing} onClick={() => void confirmRemove()}>
              {t('models.downloads.remove')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function DownloadRow({
  item,
  locale,
  selected,
  onToggle,
  onRemove,
}: {
  item: DownloadJob;
  locale: string;
  selected: boolean;
  onToggle: () => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const percent = item.total ? Math.min(100, Math.round(((item.completed ?? 0) / item.total) * 100)) : null;
  return (
    <li className={`flex items-center border-b ${selected ? 'bg-accent/60' : ''}`}>
      <div className="px-3">
        <Checkbox checked={selected} onCheckedChange={onToggle} aria-label={item.label} disabled={item.status === 'running'} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1 px-3 py-2">
        <p className="truncate text-sm font-medium">{item.label}</p>
        <p className="truncate text-xs text-muted-foreground">
          {[
            item.publisher,
            t(`models.downloads.status.${item.status}`),
            item.sizeBytes ? formatBytes(item.sizeBytes, locale) : '',
            item.status === 'running' && percent != null ? `${percent} %` : '',
            item.status === 'running' && item.rateBps ? `${formatBytes(item.rateBps, locale)}/s` : '',
          ].filter(Boolean).join(' · ')}
        </p>
        {item.status === 'running' && percent != null ? (
          <div className="h-1 overflow-hidden rounded-full bg-muted">
            <div className="h-full bg-primary" style={{ width: `${percent}%` }} />
          </div>
        ) : null}
      </div>
      <div className="flex shrink-0 flex-wrap justify-end gap-1 px-3">
        {item.status === 'running' || item.status === 'queued' ? (
          <Button type="button" size="sm" variant="outline" onClick={() => void pauseDownload(item.id)}>{t('models.downloads.pause')}</Button>
        ) : null}
        {item.status === 'paused' || item.status === 'stopped' || item.status === 'error' ? (
          <Button type="button" size="sm" variant="outline" onClick={() => void resumeDownload(item.id)}>{t('models.downloads.resume')}</Button>
        ) : null}
        {item.status === 'running' || item.status === 'queued' || item.status === 'paused' ? (
          <Button type="button" size="sm" variant="outline" onClick={() => void stopDownload(item.id)}>{t('models.downloads.stop')}</Button>
        ) : null}
        {item.status !== 'running' ? (
          <Button type="button" size="sm" variant="outline" onClick={onRemove}>{t('models.downloads.remove')}</Button>
        ) : null}
      </div>
    </li>
  );
}
