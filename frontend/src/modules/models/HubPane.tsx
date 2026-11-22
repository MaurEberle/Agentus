import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Download, RotateCcw } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
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
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ApiError, queryClient } from '@/api/client';
import { formatBytes, formatDateTime } from '@/lib/format';
import { enqueueDownload, hubFiles, listDownloads, listInstalled, searchHub } from '@/modules/models/api';
import { formatParameters, modelLabel } from '@/lib/modelName';
import { cn } from '@/lib/utils';
import { DetailHero, DetailSection, ExternalLink, FeatureBadge, KeyFacts } from '@/modules/models/ModelDetailParts';
import { HubCapabilityFilter } from '@/modules/models/HubCapabilityFilter';
import { HubContextFilter } from '@/modules/models/HubContextFilter';
import { contextLabel, gpuFit, maxFitBillions, q4Bytes, type GpuFit } from '@/modules/models/hubFit';
import { HubSizeFilter } from '@/modules/models/HubSizeFilter';
import { sizeQuery } from '@/modules/models/hubSize';
import { downloadLabel, hubLocalState, tagKey } from '@/modules/models/hubState';
import type { QuantFile } from '@/modules/models/model';
import { useHostResourcesQuery } from '@/modules/settings/api';
import { inferenceVramBytes } from '@/modules/network/inspector/vram';
import { WidthGrip } from '@/modules/monitoring/PaneGrips';
import {
  HUB_PAGE_SIZES,
  rememberHubPageSize,
  useModelsUi,
  type HubCapabilities,
  type HubCapability,
  type HubCapabilityRule,
  type HubPageSize,
  type HubPipeline,
  type HubSort,
} from '@/modules/models/store';

function clampShare(value: number): number {
  if (!Number.isFinite(value)) return 0.68;
  return Math.min(0.75, Math.max(0.6, value));
}

function useWideLayout(): boolean {
  const [wide, setWide] = useState(() => window.matchMedia('(min-width: 768px)').matches);
  useEffect(() => {
    const media = window.matchMedia('(min-width: 768px)');
    const apply = () => setWide(media.matches);
    apply();
    media.addEventListener('change', apply);
    return () => media.removeEventListener('change', apply);
  }, []);
  return wide;
}

function compactNumber(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

function yesNo(t: (key: string) => string, value: boolean): string {
  return t(value ? 'models.detail.loadedYes' : 'models.detail.loadedNo');
}

function pipelineLabel(t: (key: string) => string, pipeline?: string): string | null {
  if (pipeline === 'text-generation') return t('models.hub.types.text');
  if (pipeline === 'feature-extraction' || pipeline === 'sentence-similarity') return t('models.hub.types.embed');
  // A chat model that also sees: the Sehen badge says so.
  if (pipeline === 'image-text-to-text') return t('models.hub.types.text');
  return pipeline ?? null;
}

const PIPELINES = ['text', 'embed', 'moe'] as const satisfies readonly HubPipeline[];
type Pipeline = HubPipeline;
// The Hub sorts these only descending; a name is found with the search field.
const SORTS = ['downloads', 'likes', 'trending', 'new', 'modified'] as const satisfies readonly HubSort[];
const FIT_DOT: Record<GpuFit, string> = {
  fits: 'bg-primary',
  tight: 'bg-warning',
  large: 'bg-muted-foreground/50',
};
function freshPage(): { page: number; cursors: (string | null)[] } {
  return { page: 0, cursors: [null] };
}
let hubSearchGen = 0;
// A search that hangs gives up, so it neither keeps the pane waiting nor holds one of the
// few connections the browser opens to the app.
const SEARCH_TIMEOUT_MS = 45_000;
let hubFilesGen = 0;

function failureKey(caught: unknown): string {
  if (caught instanceof ApiError && caught.messageKey) return caught.messageKey;
  return 'models.hub.failed';
}

function knownPages(current: number, loaded: number): number[] {
  if (loaded < 6) return Array.from({ length: loaded }, (_, index) => index);
  const pages = new Set<number>([0, loaded - 1]);
  for (let index = Math.max(1, current - 1); index <= Math.min(loaded - 2, current + 1); index += 1) pages.add(index);
  return [...pages].sort((left, right) => left - right);
}

export function HubPane() {
  const { t, i18n } = useTranslation();
  const hub = useModelsUi((state) => state.hub);
  const patchHub = useModelsUi((state) => state.patchHub);
  const resetHubFilters = useModelsUi((state) => state.resetHubFilters);
  const {
    search, debounced, pipelines, minB, maxB, bounds, sort, capabilities, minContext, hideInstalled, fitsGpu,
    page, cursors, picked, quant, share,
    snapshot, files, filesError, filesNonce,
  } = hub;
  const pageSize: HubPageSize = (HUB_PAGE_SIZES as readonly number[]).includes(hub.pageSize) ? hub.pageSize : 30;
  const setSearch = (value: string) => patchHub({ search: value });
  const setDebounced = (value: string) => patchHub((current) => (
    current.debounced === value ? current : { debounced: value, ...freshPage() }
  ));
  const setPipelines = (value: Pipeline[] | ((current: Pipeline[]) => Pipeline[])) =>
    patchHub((current) => ({ pipelines: typeof value === 'function' ? value(current.pipelines) : value, ...freshPage() }));
  // Typing and dragging wait for the bounds to settle; a preset searches right away.
  const setRange = (value: { min: string; max: string }, now: boolean) =>
    patchHub((current) => ({
      minB: value.min,
      maxB: value.max,
      ...(now && (current.bounds.min !== value.min || current.bounds.max !== value.max)
        ? { bounds: value, ...freshPage() }
        : {}),
    }));
  const setBounds = (value: { min: string; max: string }) =>
    patchHub((current) => (
      current.bounds.min === value.min && current.bounds.max === value.max ? current : { bounds: value, ...freshPage() }
    ));
  const setSort = (value: HubSort) => patchHub({ sort: value, ...freshPage() });
  const setMinContext = (value: number) => patchHub({ minContext: value, ...freshPage() });
  const setHideInstalled = (value: boolean) => patchHub({ hideInstalled: value, ...freshPage() });
  const setFitsGpu = (value: boolean) => patchHub({ fitsGpu: value, ...freshPage() });
  const setPageSize = (value: HubPageSize) => patchHub({ pageSize: value, ...freshPage() });
  const setCapability = (key: HubCapability, choice: HubCapabilityRule | 'any') =>
    patchHub((current) => {
      const next: HubCapabilities = { ...current.capabilities };
      if (choice === 'any') delete next[key];
      else next[key] = choice;
      return { capabilities: next, ...freshPage() };
    });
  const setPage = (value: number | ((current: number) => number)) =>
    patchHub((current) => ({ page: typeof value === 'function' ? value(current.page) : value }));
  // A new pick must not show the previous pick's error while it loads.
  const setPicked = (value: string | null) =>
    patchHub((current) => (current.picked === value ? current : { picked: value, filesError: null }));
  const setQuant = (value: string | null) => patchHub({ quant: value });
  const [queuing, setQueuing] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const wide = useWideLayout();
  const listShare = clampShare(share);
  const cursor = cursors[page] ?? '';
  const resources = useHostResourcesQuery({ live: false });
  const vram = inferenceVramBytes(resources.data?.gpus ?? []);
  const fitMax = maxFitBillions(vram);
  const sizeCap = fitsGpu ? fitMax : null;
  // Installed models and the download queue: same queries as the models list and the
  // download header (which polls), so the marks follow a running download.
  const installedQuery = useQuery({ queryKey: ['models'], queryFn: listInstalled, gcTime: Number.POSITIVE_INFINITY });
  const downloadsQuery = useQuery({ queryKey: ['models', 'downloads'], queryFn: listDownloads });
  const local = useMemo(
    () => hubLocalState(installedQuery.data, downloadsQuery.data?.items),
    [installedQuery.data, downloadsQuery.data],
  );
  // While installed repos are hidden, a finished download refreshes the list.
  const installedKey = hideInstalled ? [...local.installedByRepo.keys()].sort().join(',') : '';
  const requestKey = JSON.stringify([
    debounced, pipelines, bounds.min, bounds.max, sort, pageSize, cursor, capabilities, page,
    minContext, hideInstalled, sizeCap, installedKey,
  ]);
  const stored = snapshot?.key === requestKey ? snapshot : null;
  const [searching, setSearching] = useState(() => !(stored && !stored.errorKey));
  const requestKeyRef = useRef(requestKey);
  if (requestKeyRef.current !== requestKey) {
    requestKeyRef.current = requestKey;
    if (searching !== true) setSearching(true);
  }
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search), 400);
    return () => window.clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    const timer = window.setTimeout(() => setBounds({ min: minB, max: maxB }), 400);
    return () => window.clearTimeout(timer);
  }, [minB, maxB]);
  useEffect(() => {
    rememberHubPageSize(pageSize);
  }, [pageSize]);
  useEffect(() => {
    const current = useModelsUi.getState().hub.snapshot;
    if (current?.key === requestKey && !current.errorKey) {
      setSearching(false);
      return;
    }
    const gen = ++hubSearchGen;
    setSearching(true);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort('timeout'), SEARCH_TIMEOUT_MS);
    const activeCursor = cursors[page] ?? '';
    void searchHub({
      search: debounced,
      pipeline: pipelines.length ? pipelines.join(',') : 'all',
      size: sizeQuery(bounds.min, bounds.max, sizeCap),
      sort,
      limit: pageSize,
      cursor: activeCursor,
      caps: Object.keys(capabilities).filter((key) => capabilities[key as keyof HubCapabilities] === 'must').join(','),
      without: Object.keys(capabilities).filter((key) => capabilities[key as keyof HubCapabilities] === 'never').join(','),
      context: minContext,
      hideInstalled,
    }, controller.signal).then((data) => {
      if (gen !== hubSearchGen) return;
      patchHub({
        snapshot: {
          key: requestKey,
          items: data.messageKey ? [] : data.items,
          hasNext: data.messageKey ? false : data.hasNext,
          nextCursor: data.messageKey ? undefined : data.nextCursor,
          errorKey: data.messageKey,
          retryAfter: data.retryAfter,
        },
      });
      setSearching(false);
    }).catch((caught: unknown) => {
      if (gen !== hubSearchGen) return;
      const timedOut = controller.signal.reason === 'timeout';
      // Replaced by a newer search or the pane closed: nothing to show.
      if (controller.signal.aborted && !timedOut) return;
      patchHub({
        snapshot: {
          key: requestKey,
          items: [],
          hasNext: false,
          errorKey: timedOut ? 'models.hub.timeout' : failureKey(caught),
        },
      });
      setSearching(false);
    }).finally(() => window.clearTimeout(timer));
    return () => {
      window.clearTimeout(timer);
      controller.abort('superseded');
    };
  }, [requestKey, attempt]);
  useEffect(() => {
    if (!picked) return;
    const current = useModelsUi.getState().hub;
    if (current.files?.id === picked && current.files.nonce === filesNonce && !current.filesError) return;
    const gen = ++hubFilesGen;
    void hubFiles(picked).then((data) => {
      if (gen !== hubFilesGen) return;
      if (data.messageKey) {
        patchHub({ files: null, filesError: data.messageKey });
        return;
      }
      patchHub({ files: { id: picked, data, nonce: filesNonce }, filesError: null });
    }).catch((caught: unknown) => {
      if (gen !== hubFilesGen) return;
      patchHub({ files: null, filesError: failureKey(caught) });
    });
  }, [picked, filesNonce]);
  const detail = files?.id === picked ? files.data : null;
  const preferred = useMemo(() => {
    const rows = detail?.quants ?? [];
    return rows.find((item) => item.quant.toLowerCase() === 'q4_k_m') ?? rows[0] ?? null;
  }, [detail]);
  useEffect(() => {
    const tags = detail?.quants ?? [];
    if (tags.length === 0) return;
    const current = useModelsUi.getState().hub.quant;
    if (current && tags.some((item) => item.tag === current)) return;
    const next = tags.find((item) => item.quant.toLowerCase() === 'q4_k_m') ?? tags[0];
    if (next) patchHub({ quant: next.tag });
  }, [detail, patchHub]);
  const chosen = (detail?.quants ?? []).find((item) => item.tag === quant) ?? preferred;
  const isInstalled = (file: QuantFile) => (local.installedKeys ? local.installedKeys.has(tagKey(file.tag)) : file.installed);
  const chosenInstalled = chosen ? isInstalled(chosen) : false;
  const chosenJob = chosen ? local.downloadByKey.get(tagKey(chosen.tag)) : undefined;
  function togglePipeline(key: Pipeline) {
    setPipelines((current) => (current.includes(key) ? current.filter((item) => item !== key) : [...current, key]));
  }
  const filtersDirty =
    search !== '' ||
    pipelines.length > 0 ||
    Object.keys(capabilities).length > 0 ||
    minB !== '' ||
    maxB !== '' ||
    minContext !== 0 ||
    hideInstalled ||
    fitsGpu ||
    sort !== 'downloads';
  function resetFilters() {
    resetHubFilters();
  }

  async function install(file: QuantFile) {
    const label = modelLabel(file.tag);
    setQueuing(true);
    try {
      await enqueueDownload({
        model: file.tag,
        label: label.name,
        publisher: label.publisher,
        sizeBytes: file.sizeBytes,
      });
      await queryClient.invalidateQueries({ queryKey: ['models', 'downloads'] });
    } finally {
      setQueuing(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t('models.hub.search')}
            aria-label={t('models.hub.search')}
            className="h-8 w-56"
          />
          <Select value={sort} onValueChange={(value) => setSort(value as HubSort)}>
            <SelectTrigger className="h-8 w-fit shrink-0 gap-1.5 [&>span]:flex-none" aria-label={t('models.hub.sort')}><SelectValue /></SelectTrigger>
            <SelectContent>
              {SORTS.map((key) => <SelectItem key={key} value={key}>{t(`models.hub.sorts.${key}`)}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-wrap items-center gap-2">
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
          <HubCapabilityFilter value={capabilities} onChoose={setCapability} />
          <HubSizeFilter
            min={minB}
            max={maxB}
            onChange={setRange}
            gpu={{ maxB: fitMax, vram: formatBytes(vram, i18n.language), on: fitsGpu, onChange: setFitsGpu }}
          />
          <HubContextFilter value={minContext} onChange={setMinContext} />
          <label className="flex h-8 shrink-0 items-center gap-2 px-1 text-xs">
            <Switch checked={hideInstalled} onCheckedChange={(value) => setHideInstalled(value === true)} />
            <span>{t('models.hub.hideInstalled')}</span>
          </label>
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="size-8"
            aria-label={t('models.hub.reset')}
            title={t('models.hub.reset')}
            disabled={!filtersDirty}
            onClick={resetFilters}
          >
            <RotateCcw className="size-4" />
          </Button>
        </div>
      </div>
      <div data-split-row className="flex min-h-0 flex-1 flex-col md:flex-row">
        <div
          className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden border-b md:border-b-0"
          style={wide ? { width: `${listShare * 100}%`, flex: 'none', minWidth: '60%' } : undefined}
        >
          {stored && !stored.errorKey && stored.items.length > 0 ? (
            <ul className="min-h-0 flex-1 overflow-auto">
              {stored.items.map((item) => {
                const repo = item.id.toLowerCase();
                const installedTags = local.installedByRepo.get(repo) ?? [];
                const job = local.downloadByRepo.get(repo);
                const fit = gpuFit(item.parameterCount, vram);
                return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setPicked(item.id)}
                    className={`flex w-full flex-col gap-0.5 border-b px-3 py-2 text-left ${picked === item.id ? 'bg-accent' : ''}`}
                  >
                    <span className="flex min-w-0 max-w-full items-center gap-1.5">
                      <ModelName value={item.id} variant="tag" className="text-sm font-medium" />
                      {installedTags.length > 0 ? (
                        <Badge
                          variant="outline"
                          className="shrink-0 gap-1 border-primary/40 bg-primary/10 px-1.5 py-0 text-[11px] text-primary"
                          title={installedTags.join('\n')}
                        >
                          <Check className="size-3" aria-hidden />
                          {installedTags.length > 1
                            ? t('models.hub.state.installedMany', { count: installedTags.length })
                            : t('models.hub.state.installed')}
                        </Badge>
                      ) : null}
                      {job ? (
                        <Badge
                          variant="outline"
                          className="shrink-0 gap-1 border-warning/50 bg-warning/10 px-1.5 py-0 text-[11px] text-foreground"
                          title={job.model}
                        >
                          <Download className="size-3" aria-hidden />
                          {downloadLabel(t, job)}
                        </Badge>
                      ) : null}
                    </span>
                    <span className="flex min-w-0 max-w-full items-center gap-1.5 text-xs text-muted-foreground">
                      {fit ? (
                        <span
                          className="inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 text-[11px] leading-4 text-foreground"
                          title={t('models.hub.fit.hint', {
                            size: formatBytes(q4Bytes(item.parameterCount ?? 0), i18n.language),
                            vram: formatBytes(vram, i18n.language),
                          })}
                        >
                          <span className={cn('size-1.5 rounded-full', FIT_DOT[fit])} aria-hidden />
                          {t(`models.hub.fit.${fit}`)}
                        </span>
                      ) : null}
                      <span className="truncate">
                        {[
                          formatParameters(item.parameters) ?? '',
                          item.contextLength ? contextLabel(item.contextLength) : '',
                          t('models.hub.downloads', { count: compactNumber(item.downloads, i18n.language) }),
                          t('models.hub.likes', { count: item.likes.toLocaleString(i18n.language) }),
                          item.vision ? t('models.badges.vision') : '',
                          item.tools ? t('models.badges.tools') : '',
                          item.thinking ? t('models.badges.thinking') : '',
                          item.moe ? t('models.badges.moe') : '',
                        ].filter(Boolean).join(' · ')}
                      </span>
                    </span>
                  </button>
                </li>
                );
              })}
            </ul>
          ) : searching ? (
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4" role="status" aria-label={t('app.loading')}>
              <BrandMark spinning className="size-24" alt="" />
              <p className="text-sm text-muted-foreground">{t('app.loading')}</p>
            </div>
          ) : stored?.errorKey ? (
            <div className="flex flex-col items-start gap-2 p-4">
              <p className="text-sm text-muted-foreground">{t(stored.errorKey, { defaultValue: t('models.hub.failed') })}</p>
              {stored.retryAfter ? (
                <p className="text-xs text-muted-foreground">{t('models.hub.retryIn', { seconds: stored.retryAfter })}</p>
              ) : null}
              <Button type="button" size="sm" variant="outline" onClick={() => setAttempt((value) => value + 1)}>
                <RotateCcw className="size-4" aria-hidden />
                {t('models.hub.retry')}
              </Button>
            </div>
          ) : (
            <p className="p-4 text-sm text-muted-foreground">{t('models.hub.empty')}</p>
          )}
          <div className="flex min-w-0 flex-nowrap items-center justify-between gap-2 border-t px-3 py-2">
            <div className="flex min-w-0 flex-nowrap items-center gap-1">
              <Button type="button" size="sm" variant="outline" disabled={page === 0 || searching} onClick={() => setPage(0)}>
                {t('models.hub.first')}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={page === 0 || searching}
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
                    disabled={searching}
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
                disabled={!stored?.hasNext || searching}
                onClick={() => {
                  const token = stored?.nextCursor;
                  if (!token) return;
                  patchHub((current) => {
                    const copy = current.cursors.slice(0, current.page + 1);
                    copy.push(token);
                    return { cursors: copy, page: current.page + 1 };
                  });
                }}
              >
                {t('models.hub.next')}
              </Button>
            </div>
            <Select value={String(pageSize)} onValueChange={(value) => setPageSize(Number(value) as HubPageSize)}>
              <SelectTrigger className="h-8 w-fit shrink-0 gap-1.5 [&>span]:flex-none" aria-label={t('models.hub.pageSize')}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {HUB_PAGE_SIZES.map((count) => (
                  <SelectItem key={count} value={String(count)}>{t('models.hub.perPage', { count })}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <WidthGrip label={t('models.split')} share={listShare} onChange={(next) => patchHub({ share: clampShare(next) })} />
        <div className="min-h-0 min-w-0 flex-1 overflow-auto md:border-l">
          {!picked ? <p className="p-4 text-sm text-muted-foreground">{t('models.hub.pick')}</p> : null}
          {picked && !detail && !filesError ? (
            <div className="flex justify-center py-10">
              <Spinner size="lg" label={t('app.loading')} />
            </div>
          ) : null}
          {filesError && picked && !detail ? (
            <p className="p-4 text-sm text-muted-foreground">{t(filesError, { defaultValue: t('models.hub.failed') })}</p>
          ) : null}
          {detail ? (
            <div className="flex min-h-full flex-col">
              <DetailHero
                title={modelLabel(detail.id).name}
                publisher={detail.author ?? modelLabel(detail.id).publisher}
                badges={
                  <>
                    {pipelineLabel(t, detail.pipeline) ? (
                      <FeatureBadge
                        kind={detail.moe ? 'moe' : undefined}
                        label={[pipelineLabel(t, detail.pipeline), detail.moe ? t('models.badges.moe') : '']
                          .filter(Boolean)
                          .join(' · ')}
                        strong
                      />
                    ) : detail.moe ? (
                      <FeatureBadge kind="moe" label={t('models.badges.moe')} strong />
                    ) : null}
                    {(local.installedByRepo.get(detail.id.toLowerCase()) ?? []).length > 0 ? (
                      <FeatureBadge live label={t('models.hub.state.installed')} />
                    ) : null}
                    {detail.tools ? <FeatureBadge kind="tools" label={t('models.badges.tools')} /> : null}
                    {detail.thinking ? <FeatureBadge kind="thinking" label={t('models.badges.thinking')} /> : null}
                    {detail.vision ? <FeatureBadge kind="vision" label={t('models.badges.vision')} /> : null}
                  </>
                }
              >
                <KeyFacts
                  items={[
                    { label: t('models.hub.detail.parameters'), value: formatParameters(detail.parameters) },
                    {
                      label: t('models.hub.detail.context'),
                      value: detail.contextLength ? new Intl.NumberFormat(i18n.language).format(detail.contextLength) : null,
                    },
                    {
                      label: t('models.hub.detail.downloads'),
                      value: detail.downloads ? compactNumber(detail.downloads, i18n.language) : null,
                      hint: detail.downloads ? detail.downloads.toLocaleString(i18n.language) : undefined,
                    },
                    {
                      label: t('models.hub.detail.likes'),
                      value: detail.likes ? compactNumber(detail.likes, i18n.language) : null,
                      hint: detail.likes ? detail.likes.toLocaleString(i18n.language) : undefined,
                    },
                  ]}
                />
              </DetailHero>
              <div className="grid gap-4 p-4">
                {/* Installing is the action of this pane: right after the figures. */}
                <section className="space-y-2 rounded-md border bg-muted/20 p-3">
                  <h3 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    {t('models.hub.install')}
                  </h3>
                  {detail.reason === 'gated' ? <p className="text-sm text-destructive">{t('models.hub.gated')}</p> : null}
                  {detail.reason === 'no-gguf' ? (
                    <p className="text-sm text-muted-foreground">{t('models.hub.noGguf')}</p>
                  ) : null}
                  <label className="grid gap-1 text-sm">
                    <span className="text-muted-foreground">{t('models.hub.quants')}</span>
                    <Select value={quant ?? ''} onValueChange={setQuant} disabled={!detail.quants.length}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {detail.quants.map((item) => {
                          const job = local.downloadByKey.get(tagKey(item.tag));
                          const state = isInstalled(item) ? t('models.hub.state.installed') : job ? downloadLabel(t, job) : '';
                          return (
                            <SelectItem key={item.tag} value={item.tag}>
                              {item.quant}
                              {item.sizeBytes ? ` · ${formatBytes(item.sizeBytes, i18n.language)}` : ''}
                              {state ? ` · ${state}` : ''}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </label>
                  {chosen?.sizeBytes && vram > 0 && chosen.sizeBytes > vram ? (
                    <p className="text-xs text-muted-foreground">{t('models.hub.vramHint')}</p>
                  ) : null}
                  {/* Locked while this quant is installed or in the download queue (queued, running, paused). */}
                  <Button
                    type="button"
                    className="w-full"
                    disabled={!chosen || chosenInstalled || Boolean(chosenJob) || !detail.installable || queuing}
                    loading={queuing}
                    onClick={() => chosen && !chosenInstalled && !chosenJob && void install(chosen)}
                  >
                    {chosenInstalled
                      ? t('models.hub.installed')
                      : chosenJob
                        ? downloadLabel(t, chosenJob)
                        : t('models.hub.install')}
                  </Button>
                  {chosenJob && !chosenInstalled ? (
                    <p className="text-xs text-muted-foreground">
                      {t('models.hub.state.busy')}{' '}
                      <Link to="/downloads" className="text-primary underline">{t('models.downloads.title')}</Link>
                    </p>
                  ) : null}
                </section>
                <DetailSection
                  title={t('models.hub.detail.groupDetails')}
                  rows={[
                    [t('models.hub.detail.architecture'), detail.architecture],
                    [t('models.hub.detail.updated'), detail.updatedAt ? formatDateTime(detail.updatedAt, i18n.language) : null],
                    [t('models.hub.detail.repo'), detail.repoBytes ? formatBytes(detail.repoBytes, i18n.language) : null],
                    [t('models.hub.detail.languages'), detail.languages?.length ? detail.languages.join(', ') : null],
                    [t('models.hub.detail.template'), yesNo(t, detail.hasTemplate)],
                  ]}
                />
                <DetailSection
                  title={t('models.hub.detail.groupSource')}
                  rows={[
                    [
                      t('models.hub.detail.base'),
                      detail.baseModel ? (
                        detail.baseUrl ? <ExternalLink href={detail.baseUrl}>{detail.baseModel}</ExternalLink> : detail.baseModel
                      ) : null,
                    ],
                    [
                      t('models.hub.detail.license'),
                      detail.license ? (
                        detail.licenseUrl ? <ExternalLink href={detail.licenseUrl}>{detail.license}</ExternalLink> : detail.license
                      ) : null,
                    ],
                    [t('models.detail.hf'), <ExternalLink key="hf" href={detail.url} />],
                  ]}
                />
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
