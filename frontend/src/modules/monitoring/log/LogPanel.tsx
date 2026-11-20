import { useEffect, useMemo, useRef } from 'react';
import { Download, FileText, Pause, Play } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { notify } from '@/lib/notifications';
import { saveExportFile } from '@/lib/saveFile';
import { fileStamp, safeFilePart, shortId } from '@/modules/monitoring/model/format';
import { logHasExtra, nodeDisplayName } from '@/modules/monitoring/model/graph';
import { entryEvents, logsToMarkdown } from '@/modules/monitoring/model/logView';
import { maskSecrets, maskText } from '@/modules/monitoring/model/mask';
import type { RunSnapshot } from '@/modules/monitoring/model/types';
import { LogDetailBody } from '@/modules/monitoring/log/LogDetailBody';
import { LogViewSwitch } from '@/modules/monitoring/log/LogViewSwitch';
import { RunLogList } from '@/modules/monitoring/log/RunLogList';
import { RunSummaryCard } from '@/modules/monitoring/log/RunSummaryCard';
import { useRunLog } from '@/modules/monitoring/log/useRunLog';
import { DetailOverlay } from '@/modules/monitoring/overlay/DetailOverlay';
import { useMonitoringStore } from '@/modules/monitoring/store';

export function LogPanel({ run }: { run: RunSnapshot | null }) {
  const { t, i18n } = useTranslation();
  const logs = useMonitoringStore((state) => state.logs);
  const view = useMonitoringStore((state) => state.logView);
  const query = useMonitoringStore((state) => state.logQuery);
  const nodeId = useMonitoringStore((state) => state.logNodeId);
  const errorsOnly = useMonitoringStore((state) => state.logErrorsOnly);
  const autoscroll = useMonitoringStore((state) => state.autoscroll);
  const unseen = useMonitoringStore((state) => state.unseenCount);
  const selectedLogId = useMonitoringStore((state) => state.selectedLogId);
  const setLogView = useMonitoringStore((state) => state.setLogView);
  const setLogQuery = useMonitoringStore((state) => state.setLogQuery);
  const setLogNodeId = useMonitoringStore((state) => state.setLogNodeId);
  const setLogErrorsOnly = useMonitoringStore((state) => state.setLogErrorsOnly);
  const setAutoscroll = useMonitoringStore((state) => state.setAutoscroll);
  const setSelectedLogId = useMonitoringStore((state) => state.setSelectedLogId);
  const clearLogFilter = useMonitoringStore((state) => state.clearLogFilter);

  const graphNodes = run?.graph.nodes;
  const names = useMemo(
    () => new Map((graphNodes ?? []).map((node) => [node.id, nodeDisplayName(node)] as const)),
    [graphNodes],
  );
  const { ctx, entries, lineOf, summary } = useRunLog(logs, names, { view, query, nodeId, errorsOnly });
  const scroller = useRef<HTMLDivElement>(null);
  const selected = logs.find((item) => item.id === selectedLogId) ?? null;
  const filterNode = run?.graph.nodes.find((item) => item.id === nodeId);
  const live = Boolean(run && run.serviceStatus === 'running' && (!run.outcome || run.outcome === 'running'));

  useEffect(() => {
    if (!autoscroll) return;
    const el = scroller.current;
    if (!el) return;
    el.scrollTop = 0;
  }, [autoscroll, entries]);

  function onScroll() {
    const el = scroller.current;
    if (!el) return;
    const atTop = el.scrollTop < 48;
    if (atTop && !autoscroll) setAutoscroll(true);
    if (!atTop && autoscroll) setAutoscroll(false);
  }

  function jumpLatest() {
    setAutoscroll(true);
    const el = scroller.current;
    if (el) el.scrollTop = 0;
  }

  function exportName(extension: string) {
    const name = run?.networkName ?? 'network';
    const id = run?.runId ?? 'run';
    return `${safeFilePart(name)}-${shortId(id)}-${fileStamp()}.${extension}`;
  }

  async function save(filename: string, blob: Blob) {
    // M17: through the host save dialog; the desktop app drops blob downloads.
    try {
      const saved = await saveExportFile(filename, blob);
      if (saved) notify({ titleKey: 'history.notify.exported', variant: 'success', persist: false });
    } catch {
      notify({ titleKey: 'history.notify.exportError', variant: 'error' });
    }
  }

  async function exportJson() {
    const lines = entryEvents(entries).map((event) =>
      JSON.stringify({
        ts: event.ts,
        level: event.level,
        runId: event.runId,
        nodeId: event.nodeId,
        nodeName: event.nodeName,
        message: maskText(event.message),
        payload: event.payload === undefined ? undefined : maskSecrets(event.payload),
        stack: event.stack ? maskText(event.stack) : undefined,
      }),
    );
    await save(exportName('jsonl'), new Blob([`${lines.join('\n')}\n`], { type: 'application/x-ndjson' }));
  }

  async function exportText() {
    const title = `${run?.networkName ?? t('monitoring.log.exportTitle')} · ${shortId(run?.runId ?? 'run')}`;
    const text = maskText(logsToMarkdown(entries, ctx, { title, summary }));
    await save(exportName('md'), new Blob([text], { type: 'text/markdown' }));
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-end gap-2">
        <LogViewSwitch value={view} onChange={setLogView} />
        <div className="min-w-[10rem] flex-1">
          <Label className="text-xs" htmlFor="monitoring-log-q">
            {t('monitoring.log.search')}
          </Label>
          <Input
            id="monitoring-log-q"
            value={query}
            onChange={(event) => setLogQuery(event.target.value)}
            placeholder={t('runLog.views.searchHint')}
          />
        </div>
        <div className="w-44">
          <Label className="text-xs">{t('monitoring.log.node')}</Label>
          <Select value={nodeId ?? 'all'} onValueChange={(value) => setLogNodeId(value === 'all' ? null : value)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('monitoring.log.allNodes')}</SelectItem>
              {(run?.graph.nodes ?? []).map((node) => (
                <SelectItem key={node.id} value={node.id}>
                  {nodeDisplayName(node)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <Checkbox checked={errorsOnly} onCheckedChange={(value) => setLogErrorsOnly(value === true)} />
          {t('monitoring.log.errorsOnly')}
        </label>
        <div className="flex flex-wrap items-center gap-2 pb-1">
          <Button type="button" size="sm" variant="outline" onClick={() => (autoscroll ? setAutoscroll(false) : jumpLatest())}>
            {autoscroll ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
            {autoscroll ? t('monitoring.log.pause') : t('monitoring.log.jumpLatest')}
          </Button>
          {!autoscroll && unseen > 0 ? (
            <Badge variant="secondary">{t('monitoring.log.newCount', { count: unseen })}</Badge>
          ) : null}
          <Button type="button" size="sm" variant="outline" onClick={() => void exportText()} disabled={entries.length === 0}>
            <FileText className="size-3.5" />
            {t('monitoring.log.exportText')}
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => void exportJson()} disabled={entries.length === 0}>
            <Download className="size-3.5" />
            {t('monitoring.log.export')}
          </Button>
        </div>
      </div>
      {filterNode ? (
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">
            {t('monitoring.graph.filterChip', { name: nodeDisplayName(filterNode) })}
          </Badge>
          <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={clearLogFilter}>
            {t('monitoring.graph.clearFilter')}
          </Button>
        </div>
      ) : null}
      {summary ? <RunSummaryCard event={summary} locale={i18n.language} /> : null}
      <div
        ref={scroller}
        onScroll={onScroll}
        className="min-h-0 flex-1 overflow-auto rounded-md border bg-muted/20 font-log text-xs"
      >
        <RunLogList
          entries={entries}
          lineOf={lineOf}
          locale={i18n.language}
          onOpen={setSelectedLogId}
          live={live}
          expandAll={query.trim().length > 0 || nodeId !== null}
          emptyText={t('monitoring.log.empty')}
        />
      </div>
      <DetailOverlay
        open={Boolean(selected && logHasExtra(selected))}
        onOpenChange={(open) => {
          if (!open) setSelectedLogId(null);
        }}
        title={t('monitoring.log.detailTitle')}
      >
        {selected ? <LogDetailBody event={selected} ctx={ctx} /> : null}
      </DetailOverlay>
    </div>
  );
}
