import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDownAZ, ArrowDownZA, ChevronDown } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { BrandMark } from '@/components/BrandMark';
import { ModelName } from '@/components/ModelName';
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
import { formatBytes, formatDateTime } from '@/lib/format';
import { hubFiles, pullModel, searchHub } from '@/modules/models/api';
import type { HubFiles, PullEvent, QuantFile } from '@/modules/models/model';
import { useHostResourcesQuery } from '@/modules/settings/api';
import { inferenceVramBytes } from '@/modules/network/inspector/vram';

function yesNo(t: (key: string) => string, value: boolean): string {
  return t(value ? 'models.detail.loadedYes' : 'models.detail.loadedNo');
}

function pipelineLabel(t: (key: string) => string, pipeline?: string): string | null {
  if (pipeline === 'text-generation') return t('models.hub.types.text');
  if (pipeline === 'feature-extraction' || pipeline === 'sentence-similarity') return t('models.hub.types.embed');
  if (pipeline === 'image-text-to-text') return t('models.hub.types.vision');
  return pipeline ?? null;
}

function HubFacts({ data }: { data: HubFiles }) {
  const { t, i18n } = useTranslation();
  const rows: [string, string][] = [
    [t('models.hub.detail.author'), data.author ?? ''],
    [t('models.hub.detail.pipeline'), pipelineLabel(t, data.pipeline) ?? ''],
    [t('models.hub.detail.downloads'), data.downloads ? data.downloads.toLocaleString(i18n.language) : ''],
    [t('models.hub.detail.likes'), data.likes ? data.likes.toLocaleString(i18n.language) : ''],
    [t('models.hub.detail.updated'), data.updatedAt ? formatDateTime(data.updatedAt, i18n.language) : ''],
    [t('models.hub.detail.architecture'), data.architecture ?? ''],
    [t('models.hub.detail.parameters'), data.parameters ?? ''],
    [t('models.hub.detail.context'), data.contextLength ? String(data.contextLength) : ''],
    [t('models.hub.detail.repo'), data.repoBytes ? formatBytes(data.repoBytes, i18n.language) : ''],
    [t('models.hub.detail.languages'), data.languages?.length ? data.languages.join(', ') : ''],
    [t('models.hub.detail.tools'), yesNo(t, data.tools)],
    [t('models.hub.detail.thinking'), yesNo(t, data.thinking)],
    [t('models.hub.detail.vision'), yesNo(t, data.vision)],
    [t('models.hub.detail.moe'), yesNo(t, data.moe)],
    [t('models.hub.detail.template'), yesNo(t, data.hasTemplate)],
  ].filter(([, value]) => value !== '') as [string, string][];
  return (
    <dl className="grid gap-2 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="grid grid-cols-[9rem_minmax(0,1fr)] gap-2">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="min-w-0 break-words">{value}</dd>
        </div>
      ))}
      {data.license ? (
        <div className="grid grid-cols-[9rem_minmax(0,1fr)] gap-2">
          <dt className="text-muted-foreground">{t('models.hub.detail.license')}</dt>
          <dd className="min-w-0 break-words">
            {data.licenseUrl ? (
              <a className="text-primary underline" href={data.licenseUrl} target="_blank" rel="noreferrer">{data.license}</a>
            ) : data.license}
          </dd>
        </div>
      ) : null}
      {data.baseModel ? (
        <div className="grid grid-cols-[9rem_minmax(0,1fr)] gap-2">
          <dt className="text-muted-foreground">{t('models.hub.detail.base')}</dt>
          <dd className="min-w-0 break-words">
            {data.baseUrl ? (
              <a className="text-primary underline" href={data.baseUrl} target="_blank" rel="noreferrer">{data.baseModel}</a>
            ) : data.baseModel}
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

const PIPELINES = ['text', 'embed', 'vision', 'moe'] as const;
type Pipeline = (typeof PIPELINES)[number];
const SIZES = ['any', '3', '8', '14', '32', '70', 'xl', 'custom'] as const;
const SORTS = ['downloads', 'likes', 'trending', 'modified', 'name'] as const;
const PAGE_SIZES = [10, 20, 30, 50, 100] as const;
const CAPABILITIES = ['tools', 'thinking', 'vision'] as const;
type Capability = (typeof CAPABILITIES)[number];
const PAGE_SIZE_KEY = 'agentus.models.hubPageSize';

function loadPageSize(): (typeof PAGE_SIZES)[number] {
  try {
    const value = Number(window.localStorage.getItem(PAGE_SIZE_KEY));
    if ((PAGE_SIZES as readonly number[]).includes(value)) return value as (typeof PAGE_SIZES)[number];
  } catch {
    // Storage can be blocked. The default page size still works.
  }
  return 30;
}

function billions(raw: string): string | null {
  const text = raw.trim().replace(',', '.');
  if (!text || !/^\d+(\.\d+)?$/.test(text)) return null;
  return text;
}

function knownPages(current: number, loaded: number): number[] {
  if (loaded <= 7) return Array.from({ length: loaded }, (_, index) => index);
  const pages = new Set<number>([0, loaded - 1]);
  for (let index = Math.max(1, current - 2); index <= Math.min(loaded - 1, current + 2); index += 1) pages.add(index);
  return [...pages].sort((left, right) => left - right);
}

function sizeQuery(size: string, minRaw: string, maxRaw: string): string {
  if (size !== 'custom') return size;
  let minimum = billions(minRaw);
  let maximum = billions(maxRaw);
  if (minimum && maximum && Number(minimum) > Number(maximum)) {
    [minimum, maximum] = [maximum, minimum];
  }
  const parts = [minimum ? `min:${minimum}B` : '', maximum ? `max:${maximum}B` : ''].filter(Boolean);
  return parts.join(',') || 'any';
}

export function HubPane() {
  const { t, i18n } = useTranslation();
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [size, setSize] = useState<(typeof SIZES)[number]>('any');
  const [minB, setMinB] = useState('');
  const [maxB, setMaxB] = useState('');
  const [bounds, setBounds] = useState({ min: '', max: '' });
  const [sort, setSort] = useState<(typeof SORTS)[number]>('downloads');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZES)[number]>(loadPageSize);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [page, setPage] = useState(0);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [picked, setPicked] = useState<string | null>(null);
  const [quant, setQuant] = useState<string | null>(null);
  const [pulling, setPulling] = useState<PullEvent | null>(null);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search), 400);
    return () => window.clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    const timer = window.setTimeout(() => setBounds({ min: minB, max: maxB }), 400);
    return () => window.clearTimeout(timer);
  }, [minB, maxB]);
  useEffect(() => {
    try {
      window.localStorage.setItem(PAGE_SIZE_KEY, String(pageSize));
    } catch {
      // Remembering the page size is optional.
    }
  }, [pageSize]);
  useEffect(() => {
    setPage(0);
    setCursors([null]);
  }, [debounced, pipelines, size, bounds.min, bounds.max, sort, sortDir, pageSize, capabilities]);
  const resources = useHostResourcesQuery({ live: false });
  const vram = inferenceVramBytes(resources.data?.gpus ?? []);
  const results = useQuery({
    queryKey: ['models', 'hub', debounced, pipelines.join(','), size, bounds.min, bounds.max, sort, sortDir, pageSize, cursors[page] ?? '', capabilities.join(',')],
    queryFn: () =>
      searchHub({
        search: debounced,
        pipeline: pipelines.length ? pipelines.join(',') : 'all',
        size: sizeQuery(size, bounds.min, bounds.max),
        sort,
        direction: sortDir,
        limit: pageSize,
        cursor: cursors[page] ?? '',
        caps: capabilities.join(','),
      }),
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
  function toggleCapability(key: Capability) {
    setCapabilities((current) => (current.includes(key) ? current.filter((item) => item !== key) : [...current, key]));
  }
  function togglePipeline(key: Pipeline) {
    setPipelines((current) => (current.includes(key) ? current.filter((item) => item !== key) : [...current, key]));
  }

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
          className="h-8 max-w-56"
        />
        <div className="flex items-center gap-1">
          <Select value={sort} onValueChange={(value) => setSort(value as typeof sort)}>
            <SelectTrigger className="h-8 w-fit shrink-0 gap-1.5 [&>span]:flex-none" aria-label={t('models.hub.sort')}><SelectValue /></SelectTrigger>
            <SelectContent>
              {SORTS.map((key) => <SelectItem key={key} value={key}>{t(`models.hub.sorts.${key}`)}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="size-8"
            aria-label={t('networks.filter.direction')}
            onClick={() => setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'))}
          >
            {sortDir === 'asc' ? <ArrowDownAZ className="size-4" /> : <ArrowDownZA className="size-4" />}
          </Button>
        </div>
        <span className="mx-1 h-6 w-px shrink-0 bg-border" aria-hidden />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 w-auto shrink-0 gap-1.5 px-2.5 text-sm font-normal shadow-sm"
              aria-label={
                pipelines.length > 0
                  ? `${t('models.hub.type')}: ${pipelines.length}`
                  : t('models.hub.type')
              }
            >
              <span>{t('models.hub.type')}</span>
              {pipelines.length > 0 ? (
                <span className="flex size-5 items-center justify-center rounded-full bg-primary text-[11px] font-medium leading-none text-primary-foreground">
                  {pipelines.length}
                </span>
              ) : null}
              <ChevronDown className="size-4 opacity-60" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            {PIPELINES.map((key) => (
              <DropdownMenuCheckboxItem
                key={key}
                checked={pipelines.includes(key)}
                onCheckedChange={() => togglePipeline(key)}
                onSelect={(event) => event.preventDefault()}
              >
                {t(`models.hub.types.${key}`)}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 w-auto shrink-0 gap-1.5 px-2.5 text-sm font-normal shadow-sm"
              aria-label={
                capabilities.length > 0
                  ? `${t('models.hub.capabilities')}: ${capabilities.length}`
                  : t('models.hub.capabilities')
              }
            >
              <span>{t('models.hub.capabilities')}</span>
              {capabilities.length > 0 ? (
                <span className="flex size-5 items-center justify-center rounded-full bg-primary text-[11px] font-medium leading-none text-primary-foreground">
                  {capabilities.length}
                </span>
              ) : null}
              <ChevronDown className="size-4 opacity-60" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            {CAPABILITIES.map((key) => (
              <DropdownMenuCheckboxItem
                key={key}
                checked={capabilities.includes(key)}
                onCheckedChange={() => toggleCapability(key)}
                onSelect={(event) => event.preventDefault()}
              >
                {t(`models.badges.${key}`)}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <Select value={size} onValueChange={(value) => setSize(value as typeof size)}>
          <SelectTrigger className="h-8 w-fit shrink-0 gap-1.5 [&>span]:flex-none" aria-label={t('models.hub.size')}>
            <SelectValue>{size === 'any' ? t('models.hub.size') : t(`models.hub.sizes.${size}`)}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            {SIZES.map((key) => <SelectItem key={key} value={key}>{t(`models.hub.sizes.${key}`)}</SelectItem>)}
          </SelectContent>
        </Select>
        {size === 'custom' ? (
          <div className="flex items-center gap-1">
            <Input
              value={minB}
              onChange={(event) => setMinB(event.target.value)}
              inputMode="decimal"
              placeholder={t('models.hub.sizes.from')}
              aria-label={t('models.hub.sizes.from')}
              aria-invalid={minB.trim() !== '' && billions(minB) == null}
              className="h-8 w-16"
            />
            <span className="text-sm text-muted-foreground">B</span>
            <span className="text-sm text-muted-foreground" aria-hidden>–</span>
            <Input
              value={maxB}
              onChange={(event) => setMaxB(event.target.value)}
              inputMode="decimal"
              placeholder={t('models.hub.sizes.to')}
              aria-label={t('models.hub.sizes.to')}
              aria-invalid={maxB.trim() !== '' && billions(maxB) == null}
              className="h-8 w-16"
            />
            <span className="text-sm text-muted-foreground">B</span>
          </div>
        ) : null}
      </div>
      <div className="grid min-h-0 flex-1 md:grid-cols-[minmax(0,1fr)_minmax(18rem,22rem)]">
        <div className="flex min-h-0 flex-col overflow-hidden border-b md:border-b-0 md:border-r">
          {results.isFetching ? (
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4" role="status" aria-label={t('app.loading')}>
              <BrandMark spinning className="size-24" alt="" />
              <p className="text-sm text-muted-foreground">{t('app.loading')}</p>
            </div>
          ) : results.data?.messageKey ? (
            <p className="p-4 text-sm text-muted-foreground">{t('models.hub.failed')}</p>
          ) : (results.data?.items.length ?? 0) === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">{t('models.hub.empty')}</p>
          ) : (
            <ul className="min-h-0 flex-1 overflow-auto">
              {(results.data?.items ?? []).map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setPicked(item.id)}
                    className={`flex w-full flex-col gap-0.5 border-b px-3 py-2 text-left ${picked === item.id ? 'bg-accent' : ''}`}
                  >
                    <ModelName value={item.id} variant="tag" className="text-sm font-medium" />
                    <span className="truncate text-xs text-muted-foreground">
                      {[
                        t('models.hub.downloads', { count: item.downloads.toLocaleString(i18n.language) }),
                        item.vision ? t('models.badges.vision') : '',
                        item.tools ? t('models.badges.tools') : '',
                        item.thinking ? t('models.badges.thinking') : '',
                        item.moe ? t('models.badges.moe') : '',
                      ].filter(Boolean).join(' · ')}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2 border-t px-3 py-2">
            <div className="flex flex-wrap items-center gap-1">
              <Button type="button" size="sm" variant="outline" disabled={page === 0 || results.isFetching} onClick={() => setPage(0)}>
                {t('models.hub.first')}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={page === 0 || results.isFetching}
                onClick={() => setPage((current) => Math.max(0, current - 1))}
              >
                {t('models.hub.previous')}
              </Button>
              {knownPages(page, cursors.length).map((index, position, all) => (
                <span key={index} className="flex items-center gap-1">
                  {position > 0 && all[position - 1] !== index - 1 ? <span className="px-1 text-xs text-muted-foreground">…</span> : null}
                  <Button
                    type="button"
                    size="sm"
                    variant={index === page ? 'secondary' : 'outline'}
                    className="min-w-8 px-2"
                    disabled={results.isFetching}
                    aria-current={index === page ? 'page' : undefined}
                    onClick={() => setPage(index)}
                  >
                    {index + 1}
                  </Button>
                </span>
              ))}
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={!results.data?.hasNext || results.isFetching}
                onClick={() => {
                  const token = results.data?.nextCursor;
                  if (!token) return;
                  setCursors((current) => {
                    const copy = current.slice(0, page + 1);
                    copy.push(token);
                    return copy;
                  });
                  setPage((current) => current + 1);
                }}
              >
                {t('models.hub.next')}
              </Button>
            </div>
            <Select value={String(pageSize)} onValueChange={(value) => setPageSize(Number(value) as (typeof PAGE_SIZES)[number])}>
              <SelectTrigger className="h-8 w-fit shrink-0 gap-1.5 [&>span]:flex-none" aria-label={t('models.hub.pageSize')}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZES.map((count) => (
                  <SelectItem key={count} value={String(count)}>{t('models.hub.perPage', { count })}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
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
              <HubFacts data={files.data} />
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
              <a className="text-sm text-primary underline" href={files.data.url} target="_blank" rel="noreferrer">{t('models.hub.open')}</a>
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
