import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { notify } from '@/lib/notifications';
import { ApiError } from '@/api/client';
import { isHistoryStoreOk } from '@/modules/dashboard/model';
import { listNetworkSummaries } from '@/modules/network/api';
import { useStoresQuery } from '@/modules/settings/api';
import { deleteRuns, deleteRunsOlderThan, getRun, listCalls, listRunLogs, listRuns, toApiFilter } from '@/modules/history/api';
import { RunsChart } from '@/modules/history/chart/RunsChart';
import { RunDetailPanel } from '@/modules/history/detail/RunDetailPanel';
import { ErrorTop } from '@/modules/history/errors/ErrorTop';
import { FilterBar } from '@/modules/history/filters/FilterBar';
import { KpiRow } from '@/modules/history/kpi/KpiRow';
import { RunList } from '@/modules/history/list/RunList';
import { endOfLocalDay, fileStamp, modelKey, safeFilePart, shortId, startOfLocalDay } from '@/modules/history/model/format';
import { maskLog, maskText } from '@/modules/monitoring/model/mask';
import { downloadBlob, zipStore } from '@/modules/networks/model/zip';
import { aggregateModels, aggregateNetworks, computeChart, computeErrorTop, computeKpis } from '@/modules/history/model/stats';
import {
  defaultHistoryFilter,
  historySearchFrom,
  parseHistorySearch,
  resolveBounds,
  sameFilter,
} from '@/modules/history/model/url';
import { PAGE_SIZE, STATS_LIMIT, type ErrorTopRow, type HistoryFilter, type LogEvent } from '@/modules/history/model/types';
import { HistoryRibbon } from '@/modules/history/ribbon/Ribbon';
import { useHistoryUi } from '@/modules/history/store';
import { ByModelTable } from '@/modules/history/tables/ByModelTable';
import { ByNetworkTable } from '@/modules/history/tables/ByNetworkTable';
import { cn } from '@/lib/utils';
import { moduleCardBodyClass, moduleCardClass } from '@/modules/moduleCard';


export function HistoryModule() {
  const { t, i18n } = useTranslation();
  const { runId } = useParams<{ runId: string }>();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const desktop = useMediaQuery('(min-width: 768px)');
  const queryClient = useQueryClient();
  const stores = useStoresQuery();
  const historyOk = isHistoryStoreOk(stores.data);
  const filter = useMemo(() => parseHistorySearch(params), [params]);
  const bounds = useMemo(() => resolveBounds(filter), [filter]);

  const selectedIds = useHistoryUi((state) => state.selectedIds);
  const clearSelection = useHistoryUi((state) => state.clearSelection);
  const pruneSelection = useHistoryUi((state) => state.pruneSelection);
  const setDetailTab = useHistoryUi((state) => state.setDetailTab);

  const [busy, setBusy] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [purgeOpen, setPurgeOpen] = useState(false);

  const apiFilter = useMemo(
    () =>
      toApiFilter(
        {
          from: bounds.from.toISOString(),
          to: bounds.to.toISOString(),
          networkId: filter.networkId,
          outcomes: filter.outcomes,
          model: filter.model,
          q: filter.q,
        },
        { limit: STATS_LIMIT, offset: 0 },
      ),
    [bounds.from, bounds.to, filter.model, filter.networkId, filter.outcomes, filter.q],
  );

  const runsQuery = useQuery({
    queryKey: ['runs', 'history', apiFilter],
    queryFn: () => listRuns(apiFilter),
    enabled: historyOk,
  });
  const callsQuery = useQuery({
    queryKey: ['runs', 'calls', apiFilter],
    queryFn: () => listCalls(apiFilter),
    enabled: historyOk,
  });
  const networksQuery = useQuery({
    queryKey: ['networks'],
    queryFn: listNetworkSummaries,
  });
  const detailQuery = useQuery({
    queryKey: ['runs', runId],
    queryFn: () => getRun(runId ?? ''),
    enabled: Boolean(runId) && historyOk,
  });
  const logsQuery = useQuery({
    queryKey: ['runs', runId, 'logs'],
    queryFn: () => listRunLogs(runId ?? ''),
    enabled: Boolean(runId) && historyOk,
  });
  const purgePreview = useQuery({
    queryKey: ['runs', 'purge-preview'],
    queryFn: () =>
      listRuns({
        to: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
        limit: STATS_LIMIT,
      }),
    enabled: purgeOpen && historyOk,
  });

  const items = useMemo(() => runsQuery.data?.items ?? [], [runsQuery.data?.items]);
  const total = runsQuery.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const page = Math.min(filter.page, pageCount);
  const pageItems = items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const kpis = useMemo(() => computeKpis(items), [items]);
  const buckets = useMemo(() => computeChart(items, bounds.from, bounds.to, i18n.language), [bounds.from, bounds.to, i18n.language, items]);
  const errors = useMemo(() => computeErrorTop(items), [items]);
  const modelRows = useMemo(() => aggregateModels(callsQuery.data ?? []), [callsQuery.data]);
  const networkRows = useMemo(() => aggregateNetworks(items), [items]);

  const modelOptions = useMemo(() => {
    const set = new Set<string>();
    for (const run of items) {
      for (const model of run.models) set.add(modelKey(model.provider, model.model));
    }
    if (filter.model) set.add(filter.model);
    return [...set].sort();
  }, [filter.model, items]);

  const networkOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const net of networksQuery.data?.items ?? []) map.set(net.id, net.name);
    for (const run of items) map.set(run.networkId, run.networkName);
    return [...map.entries()].map(([id, name]) => ({ id, name }));
  }, [items, networksQuery.data?.items]);

  useEffect(() => {
    pruneSelection(items.map((item) => item.runId));
  }, [items, pruneSelection]);

  useEffect(() => {
    setDetailTab('log');
  }, [runId, setDetailTab]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      if (deleteOpen || purgeOpen) return;
      clearSelection();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [clearSelection, deleteOpen, purgeOpen]);

  function applyFilter(next: HistoryFilter) {
    const paramsNext = historySearchFrom(next);
    if (sameFilter(parseHistorySearch(paramsNext), parseHistorySearch(params)) && params.toString() === paramsNext.toString()) {
      return;
    }
    setParams(paramsNext, { replace: true });
  }

  function patchFilter(patch: Partial<HistoryFilter>) {
    const merged: HistoryFilter = { ...filter, ...patch };
    if (patch.from && patch.from.length <= 10) {
      merged.from = startOfLocalDay(patch.from).toISOString();
    }
    if (patch.to && patch.to.length <= 10) {
      merged.to = endOfLocalDay(patch.to).toISOString();
    }
    if (patch.range && patch.range !== 'custom') {
      const nextBounds = resolveBounds({ ...merged, range: patch.range });
      merged.from = nextBounds.from.toISOString();
      merged.to = nextBounds.to.toISOString();
    }
    applyFilter(merged);
  }

  function openRun(id: string) {
    const search = historySearchFrom(filter).toString();
    navigate(`/history/${id}${search ? `?${search}` : ''}`);
  }

  function closeDetail() {
    const search = historySearchFrom(filter).toString();
    navigate(`/history${search ? `?${search}` : ''}`);
  }

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['runs'] });
  }

  async function confirmDelete() {
    const ids = selectedIds.filter((id) => items.find((item) => item.runId === id)?.outcome !== 'running');
    const skipped = selectedIds.length - ids.length;
    if (ids.length === 0) {
      notify({ titleKey: 'history.notify.runningDelete', variant: 'warning' });
      setDeleteOpen(false);
      return;
    }
    setBusy(true);
    try {
      await deleteRuns(ids);
      notify({
        titleKey: 'history.notify.deleted',
        values: { count: String(ids.length) },
        variant: 'success',
      });
      if (skipped) notify({ titleKey: 'history.notify.runningSkipped', variant: 'warning', persist: false });
      clearSelection();
      if (runId && ids.includes(runId)) closeDetail();
      await refresh();
    } catch (error) {
      notify({
        titleKey: error instanceof ApiError && error.messageKey ? error.messageKey : 'history.notify.error',
        variant: 'error',
      });
    } finally {
      setBusy(false);
      setDeleteOpen(false);
    }
  }

  async function confirmPurge() {
    setBusy(true);
    try {
      const result = await deleteRunsOlderThan(90);
      notify({
        titleKey: 'history.notify.purged',
        values: { count: String(result.deleted) },
        variant: 'success',
      });
      clearSelection();
      await refresh();
    } catch {
      notify({ titleKey: 'history.notify.error', variant: 'error' });
    } finally {
      setBusy(false);
      setPurgeOpen(false);
    }
  }

  async function exportIds(ids: string[]) {
    setBusy(true);
    try {
      const files: Array<{ name: string; data: Uint8Array }> = [];
      const encoder = new TextEncoder();
      for (const id of ids) {
        const run = items.find((item) => item.runId === id);
        const logs = await listRunLogs(id);
        const body = logsToJsonl(logs);
        files.push({
          name: `${safeFilePart(run?.networkName ?? 'run')}-${shortId(id)}-${fileStamp()}.jsonl`,
          data: encoder.encode(body),
        });
      }
      if (files.length === 1 && files[0]) {
        downloadBlob(files[0].name, new Blob([files[0].data], { type: 'application/x-ndjson' }));
      } else {
        downloadBlob(`history-logs-${fileStamp()}.zip`, zipStore(files));
      }
      notify({ titleKey: 'history.notify.exported', variant: 'success', persist: false });
    } catch {
      notify({ titleKey: 'history.notify.exportError', variant: 'error' });
    } finally {
      setBusy(false);
    }
  }

  function onPickError(row: ErrorTopRow) {
    patchFilter({ q: row.errorClass, tab: 'history', page: 1 });
  }

  const emptyAll = !runsQuery.isLoading && total === 0 && !filter.q && !filter.networkId && !filter.model && filter.outcomes.length === 0 && filter.range === '7d';
  const emptyFiltered = !runsQuery.isLoading && total === 0 && !emptyAll;
  const showDetail = Boolean(runId);
  const missing = Boolean(runId && detailQuery.isFetched && !detailQuery.data);

  const listPane = (
    <div className="min-w-0">
      {emptyAll ? (
        <p className="p-4 text-sm text-muted-foreground">{t('history.empty.none')}</p>
      ) : emptyFiltered ? (
        <div className="space-y-2 p-4">
          <p className="text-sm text-muted-foreground">{t('history.empty.filtered')}</p>
          <Button type="button" size="sm" variant="outline" onClick={() => applyFilter(defaultHistoryFilter())}>
            {t('history.filter.reset')}
          </Button>
        </div>
      ) : (
        <RunList items={pageItems} loading={runsQuery.isLoading} activeId={runId} onOpen={openRun} />
      )}
      {pageCount > 1 ? (
        <div className="flex items-center justify-between gap-2 px-3 py-2 text-xs text-muted-foreground">
          <span>{t('history.list.page', { page, pages: pageCount })}</span>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => patchFilter({ page: page - 1 })}
            >
              {t('history.list.prev')}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={page >= pageCount}
              onClick={() => patchFilter({ page: page + 1 })}
            >
              {t('history.list.next')}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );

  const detailPane = (
    <RunDetailPanel
      detail={detailQuery.data ?? null}
      logs={logsQuery.data ?? []}
      loading={Boolean(runId) && detailQuery.isLoading}
      missing={missing}
      onExport={() => {
        if (runId) void exportIds([runId]);
      }}
    />
  );

  return (
    <div className="flex min-h-full w-full min-w-0 flex-col gap-4 p-4 pb-24 md:p-6 md:pb-24">
      <h1 className="text-xl font-semibold tracking-tight">{t('history.title')}</h1>
      <HistoryRibbon
        selectedCount={selectedIds.length}
        busy={busy}
        onRefresh={() => void refresh()}
        onDelete={() => setDeleteOpen(true)}
        onExport={() => void exportIds(selectedIds)}
        onPurge={() => setPurgeOpen(true)}
      />
      <FilterBar
        filter={filter}
        networks={networkOptions}
        models={modelOptions}
        onChange={patchFilter}
        onReset={() => applyFilter(defaultHistoryFilter())}
      />
      {!historyOk ? (
        <Alert>
          <AlertTitle>{t('history.error.store')}</AlertTitle>
          <AlertDescription>
            <Button asChild size="sm" variant="outline" className="mt-2">
              <Link to="/settings#data">{t('history.error.openData')}</Link>
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      {runsQuery.isError ? (
        <Alert variant="destructive">
          <AlertTitle>{t('history.error.api')}</AlertTitle>
          <AlertDescription>
            <Button type="button" size="sm" variant="outline" className="mt-2" loading={runsQuery.isFetching} onClick={() => void refresh()}>
              {t('history.ribbon.refresh')}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      {historyOk ? (
        <>
          <KpiRow kpis={kpis} loading={runsQuery.isLoading} />
          <div className="grid w-full gap-4 lg:grid-cols-2 lg:items-start">
            <RunsChart buckets={buckets} />
            <ErrorTop rows={errors} onPick={onPickError} />
          </div>
          <div className="flex gap-1 border-b" role="tablist">
            {(['history', 'model', 'network'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={filter.tab === tab}
                className={cn(
                  'rounded-t-md px-3 py-2 text-sm font-medium',
                  filter.tab === tab ? 'bg-background text-foreground' : 'text-muted-foreground hover:text-foreground',
                )}
                onClick={() => patchFilter({ tab })}
              >
                {t(`history.tab.${tab}`)}
              </button>
            ))}
          </div>
          {filter.tab === 'model' ? (
            <Card className={moduleCardClass}>
              <CardContent className={cn(moduleCardBodyClass, 'p-0')}>
                <ByModelTable rows={modelRows} />
              </CardContent>
            </Card>
          ) : null}
          {filter.tab === 'network' ? (
            <Card className={moduleCardClass}>
              <CardContent className={cn(moduleCardBodyClass, 'p-0')}>
                <ByNetworkTable rows={networkRows} />
              </CardContent>
            </Card>
          ) : null}
          {filter.tab === 'history' ? (
            desktop ? (
              <div className="grid w-full gap-3 md:grid-cols-2 md:items-start">
                <Card className={cn(moduleCardClass, 'min-w-0')}>
                  <div className={cn(moduleCardBodyClass, 'overflow-x-auto')}>{listPane}</div>
                </Card>
                <Card className={cn(moduleCardClass, 'min-w-0')}>
                  <div className={moduleCardBodyClass}>{detailPane}</div>
                </Card>
              </div>
            ) : (
              <>
                <Card className={cn(moduleCardClass, 'min-w-0')}>
                  <div className={cn(moduleCardBodyClass, 'overflow-x-auto')}>{listPane}</div>
                </Card>
                <Sheet open={showDetail} onOpenChange={(open) => !open && closeDetail()}>
                  <SheetContent side="bottom" closeLabel={t('history.close')} className="max-h-[min(90vh,1000px)] overflow-auto">
                    <SheetHeader>
                      <SheetTitle>{t('history.detail.title')}</SheetTitle>
                    </SheetHeader>
                    {detailPane}
                  </SheetContent>
                </Sheet>
              </>
            )
          ) : null}
        </>
      ) : null}

      {deleteOpen ? (
        <ConfirmBar
          title={t('history.delete.title')}
          body={t('history.delete.body', { count: selectedIds.length })}
          confirm={t('history.delete.confirm')}
          cancel={t('history.delete.cancel')}
          busy={busy}
          onCancel={() => setDeleteOpen(false)}
          onConfirm={() => void confirmDelete()}
        />
      ) : null}
      {purgeOpen ? (
        <ConfirmBar
          title={t('history.retention.title')}
          body={t('history.retention.body', { count: purgePreview.data?.total ?? 0 })}
          confirm={t('history.retention.confirm')}
          cancel={t('history.delete.cancel')}
          busy={busy}
          onCancel={() => setPurgeOpen(false)}
          onConfirm={() => void confirmPurge()}
        />
      ) : null}
    </div>
  );
}

function logsToJsonl(logs: LogEvent[]): string {
  return `${logs
    .map((event) => {
      const masked = maskLog(event);
      return JSON.stringify({
        ts: event.ts,
        level: event.level,
        runId: event.runId,
        nodeId: event.nodeId,
        nodeName: event.nodeName,
        message: maskText(masked.message),
        payload: masked.payload,
        stack: masked.stack,
      });
    })
    .join('\n')}\n`;
}

function ConfirmBar({
  title,
  body,
  confirm,
  cancel,
  busy,
  onConfirm,
  onCancel,
}: {
  title: string;
  body: string;
  confirm: string;
  cancel: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-lg border bg-background p-4 shadow-lg">
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{body}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            {cancel}
          </Button>
          <Button type="button" variant="destructive" loading={busy} onClick={onConfirm}>
            {confirm}
          </Button>
        </div>
      </div>
    </div>
  );
}
