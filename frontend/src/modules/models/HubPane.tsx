import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { queryClient } from '@/api/client';
import { formatBytes } from '@/lib/format';
import { hubFiles, pullModel, searchHub } from '@/modules/models/api';
import type { PullEvent, QuantFile } from '@/modules/models/model';
import { useHostResourcesQuery } from '@/modules/settings/api';
import { inferenceVramBytes } from '@/modules/network/inspector/vram';

const PIPELINES = ['text', 'embed', 'vision'] as const;
const SIZES = ['any', '3', '8', '14', '32', '70', 'xl'] as const;
const SORTS = ['downloads', 'likes', 'trending', 'modified'] as const;

export function HubPane() {
  const { t, i18n } = useTranslation();
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const [pipeline, setPipeline] = useState<(typeof PIPELINES)[number]>('text');
  const [size, setSize] = useState<(typeof SIZES)[number]>('any');
  const [sort, setSort] = useState<(typeof SORTS)[number]>('downloads');
  const [picked, setPicked] = useState<string | null>(null);
  const [quant, setQuant] = useState<string | null>(null);
  const [pulling, setPulling] = useState<PullEvent | null>(null);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search), 400);
    return () => window.clearTimeout(timer);
  }, [search]);
  const resources = useHostResourcesQuery({ live: false });
  const vram = inferenceVramBytes(resources.data?.gpus ?? []);
  const results = useQuery({
    queryKey: ['models', 'hub', debounced, pipeline, size, sort],
    queryFn: () => searchHub({ search: debounced, pipeline, size, sort }),
  });
  const files = useQuery({
    queryKey: ['models', 'hub', 'files', picked],
    queryFn: () => hubFiles(picked ?? ''),
    enabled: Boolean(picked),
  });
  const preferred = useMemo(() => {
    const rows = files.data?.quants ?? [];
    return rows.find((item) => item.quant.toLowerCase() === 'q4_k_m') ?? rows[0] ?? null;
  }, [files.data]);
  useEffect(() => {
    setQuant(preferred?.tag ?? null);
  }, [preferred]);
  const chosen = (files.data?.quants ?? []).find((item) => item.tag === quant) ?? preferred;

  async function install(file: QuantFile) {
    const controller = new AbortController();
    abortRef.current = controller;
    setPulling({ status: 'pulling' });
    try {
      await pullModel(file.tag, (event) => setPulling(event), controller.signal);
      await queryClient.invalidateQueries({ queryKey: ['models'] });
    } catch {
      if (!controller.signal.aborted) setPulling({ status: 'error', messageKey: 'models.pull.failed' });
    }
  }

  const pullingBusy = Boolean(pulling && pulling.status !== 'error' && pulling.status !== 'success');

  const percent =
    pulling?.completed && pulling.total ? Math.min(100, Math.round((pulling.completed / pulling.total) * 100)) : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t('models.hub.search')}
          aria-label={t('models.hub.search')}
          className="h-8 max-w-xs"
        />
        <Select value={pipeline} onValueChange={(value) => setPipeline(value as typeof pipeline)}>
          <SelectTrigger className="w-40" aria-label={t('models.hub.type')}><SelectValue /></SelectTrigger>
          <SelectContent>
            {PIPELINES.map((key) => <SelectItem key={key} value={key}>{t(`models.hub.types.${key}`)}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={size} onValueChange={(value) => setSize(value as typeof size)}>
          <SelectTrigger className="w-36" aria-label={t('models.hub.size')}><SelectValue /></SelectTrigger>
          <SelectContent>
            {SIZES.map((key) => <SelectItem key={key} value={key}>{t(`models.hub.sizes.${key}`)}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={sort} onValueChange={(value) => setSort(value as typeof sort)}>
          <SelectTrigger className="w-36" aria-label={t('models.hub.sort')}><SelectValue /></SelectTrigger>
          <SelectContent>
            {SORTS.map((key) => <SelectItem key={key} value={key}>{t(`models.hub.sorts.${key}`)}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="grid min-h-0 flex-1 md:grid-cols-[minmax(0,1fr)_minmax(18rem,22rem)]">
        <div className="min-h-0 overflow-auto border-b md:border-b-0 md:border-r">
          {results.isFetching && !results.data ? (
            <div className="flex flex-1 items-center justify-center p-10">
              <Spinner size="lg" label={t('app.loading')} />
            </div>
          ) : null}
          {results.isFetching && results.data ? (
            <div className="flex items-center gap-2 border-b px-3 py-2 text-xs text-muted-foreground">
              <Spinner size="sm" label={t('app.loading')} />
              <span>{t('app.loading')}</span>
            </div>
          ) : null}
          {results.data?.messageKey ? <p className="p-4 text-sm text-muted-foreground">{t('models.hub.failed')}</p> : null}
          {(results.data?.items.length ?? 0) === 0 && !results.isFetching ? (
            <p className="p-4 text-sm text-muted-foreground">{t('models.hub.empty')}</p>
          ) : (
            <ul>
              {results.data?.items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setPicked(item.id)}
                    className={`flex w-full flex-col gap-0.5 border-b px-3 py-2 text-left ${picked === item.id ? 'bg-accent' : ''}`}
                  >
                    <span className="truncate text-sm font-medium">{item.id}</span>
                    <span className="text-xs text-muted-foreground">
                      {t('models.hub.downloads', { count: item.downloads.toLocaleString(i18n.language) })}
                      {item.pipeline ? ` · ${item.pipeline}` : ''}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="min-h-0 overflow-auto p-3">
          {!picked ? <p className="text-sm text-muted-foreground">{t('models.hub.pick')}</p> : null}
          {picked && files.isFetching && !files.data ? (
            <div className="flex justify-center py-10">
              <Spinner size="lg" label={t('app.loading')} />
            </div>
          ) : null}
          {picked && files.isFetching && files.data ? (
            <div className="mb-3 flex items-center gap-2 text-xs text-muted-foreground">
              <Spinner size="sm" label={t('app.loading')} />
              <span>{t('app.loading')}</span>
            </div>
          ) : null}
          {files.data?.reason === 'gated' ? <p className="text-sm text-destructive">{t('models.hub.gated')}</p> : null}
          {files.data?.reason === 'no-gguf' ? <p className="text-sm text-muted-foreground">{t('models.hub.noGguf')}</p> : null}
          {files.data ? (
            <div className="grid gap-3">
              <a className="text-sm text-primary underline" href={files.data.url} target="_blank" rel="noreferrer">{t('models.hub.open')}</a>
              {files.data.architecture ? <p className="text-xs text-muted-foreground">{files.data.architecture}{files.data.contextLength ? ` · ${files.data.contextLength}` : ''}</p> : null}
              <label className="grid gap-1 text-sm">
                {t('models.hub.quants')}
                <Select value={quant ?? ''} onValueChange={setQuant} disabled={!files.data.quants.length}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {files.data.quants.map((item) => (
                      <SelectItem key={item.tag} value={item.tag}>
                        {item.quant}{item.sizeBytes ? ` · ${formatBytes(item.sizeBytes, i18n.language)}` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
              {chosen?.sizeBytes && vram > 0 && chosen.sizeBytes > vram ? (
                <p className="text-xs text-muted-foreground">{t('models.hub.vramHint')}</p>
              ) : null}
              <Button
                type="button"
                disabled={!chosen || chosen.installed || !files.data.installable || pullingBusy}
                loading={pullingBusy}
                onClick={() => chosen && void install(chosen)}
              >
                {chosen?.installed ? t('models.hub.installed') : t('models.hub.install')}
              </Button>
            </div>
          ) : null}
        </div>
      </div>
      <Dialog open={Boolean(pulling)} onOpenChange={(next) => !next && !pullingBusy && setPulling(null)}>
        <DialogContent closeLabel={t('models.dialog.close')}>
          <DialogHeader>
            <DialogTitle>{t('models.hub.progress')}</DialogTitle>
          </DialogHeader>
          <p className="flex items-center gap-2 text-sm">
            {pullingBusy ? <Spinner size="sm" label={t('app.loading')} /> : null}
            <span>
              {pulling?.messageKey ? t(pulling.messageKey) : pulling?.status}
              {percent != null ? ` · ${percent}%` : ''}
            </span>
          </p>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                abortRef.current?.abort();
                setPulling(null);
              }}
            >
              {t('models.hub.cancel')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
