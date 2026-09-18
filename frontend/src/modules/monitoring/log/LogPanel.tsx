import { useEffect, useMemo, useRef } from 'react';
import {
  AlertTriangle,
  Bug,
  Download,
  Info,
  OctagonAlert,
  Pause,
  Play,
} from 'lucide-react';
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
import { cn } from '@/lib/utils';
import { fileStamp, formatTime, safeFilePart, shortId } from '@/modules/monitoring/model/format';
import { filterLogs, logHasExtra, nodeDisplayName } from '@/modules/monitoring/model/graph';
import { maskSecrets, maskText } from '@/modules/monitoring/model/mask';
import type { LogEvent, LogLevel, RunSnapshot } from '@/modules/monitoring/model/types';
import { LOG_LEVELS } from '@/modules/monitoring/model/types';
import { DetailOverlay } from '@/modules/monitoring/overlay/DetailOverlay';
import { useMonitoringStore } from '@/modules/monitoring/store';

const LEVEL_ICON = {
  debug: Bug,
  info: Info,
  warn: AlertTriangle,
  error: OctagonAlert,
};

const LEVEL_ROW: Record<LogLevel, string> = {
  debug: 'border-l-2 border-l-muted-foreground/50 bg-muted/40 text-muted-foreground',
  info: 'border-l-2 border-l-primary/60 bg-card',
  warn: 'border-l-2 border-l-warning bg-warning/20',
  error: 'border-l-2 border-l-destructive bg-destructive/15',
};

const LEVEL_BADGE: Record<LogLevel, string> = {
  debug: 'bg-muted text-muted-foreground',
  info: 'bg-primary/15 text-primary',
  warn: 'bg-warning text-warning-foreground',
  error: 'bg-destructive text-destructive-foreground',
};

export function LogPanel({ run }: { run: RunSnapshot | null }) {
  const { t, i18n } = useTranslation();
  const logs = useMonitoringStore((state) => state.logs);
  const levelMin = useMonitoringStore((state) => state.logLevelMin);
  const query = useMonitoringStore((state) => state.logQuery);
  const nodeId = useMonitoringStore((state) => state.logNodeId);
  const errorsOnly = useMonitoringStore((state) => state.logErrorsOnly);
  const autoscroll = useMonitoringStore((state) => state.autoscroll);
  const unseen = useMonitoringStore((state) => state.unseenCount);
  const selectedLogId = useMonitoringStore((state) => state.selectedLogId);
  const setLogLevelMin = useMonitoringStore((state) => state.setLogLevelMin);
  const setLogQuery = useMonitoringStore((state) => state.setLogQuery);
  const setLogNodeId = useMonitoringStore((state) => state.setLogNodeId);
  const setLogErrorsOnly = useMonitoringStore((state) => state.setLogErrorsOnly);
  const setAutoscroll = useMonitoringStore((state) => state.setAutoscroll);
  const setSelectedLogId = useMonitoringStore((state) => state.setSelectedLogId);
  const clearLogFilter = useMonitoringStore((state) => state.clearLogFilter);

  const scroller = useRef<HTMLDivElement>(null);
  const filtered = useMemo(
    () => filterLogs(logs, { levelMin, query, nodeId, errorsOnly }),
    [errorsOnly, levelMin, logs, nodeId, query],
  );
  const visible = useMemo(() => filtered.slice().reverse(), [filtered]);
  const selected = logs.find((item) => item.id === selectedLogId) ?? null;
  const filterNode = run?.graph.nodes.find((item) => item.id === nodeId);

  useEffect(() => {
    if (!autoscroll) return;
    const el = scroller.current;
    if (!el) return;
    el.scrollTop = 0;
  }, [autoscroll, visible]);

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

  function exportVisible() {
    const name = run?.networkName ?? 'network';
    const id = run?.runId ?? 'run';
    const lines = filtered.map((event) =>
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
    const blob = new Blob([`${lines.join('\n')}\n`], { type: 'application/x-ndjson' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${safeFilePart(name)}-${shortId(id)}-${fileStamp()}.jsonl`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-36">
          <Label className="text-xs">{t('monitoring.log.level')}</Label>
          <Select value={levelMin} onValueChange={(value) => setLogLevelMin(value as LogLevel)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LOG_LEVELS.map((level) => (
                <SelectItem key={level} value={level}>
                  {t('monitoring.log.levelFrom', { level: t(`monitoring.level.${level}`) })}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="min-w-[10rem] flex-1">
          <Label className="text-xs" htmlFor="monitoring-log-q">
            {t('monitoring.log.search')}
          </Label>
          <Input
            id="monitoring-log-q"
            value={query}
            onChange={(event) => setLogQuery(event.target.value)}
            placeholder={t('monitoring.log.search')}
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
          <Button type="button" size="sm" variant="outline" onClick={exportVisible} disabled={filtered.length === 0}>
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
      <div
        ref={scroller}
        onScroll={onScroll}
        className="max-h-[min(28rem,50vh)] min-h-[12rem] overflow-auto rounded-md border bg-muted/20 font-mono text-xs"
      >
        {visible.length === 0 ? (
          <p className="p-3 font-sans text-sm text-muted-foreground">{t('monitoring.log.empty')}</p>
        ) : (
          <ul>
            {visible.map((event) => (
              <LogRow
                key={event.id}
                event={event}
                locale={i18n.language}
                onOpen={() => setSelectedLogId(event.id)}
              />
            ))}
          </ul>
        )}
      </div>
      <LogDetail event={selected} onClose={() => setSelectedLogId(null)} locale={i18n.language} />
    </div>
  );
}

function LogRow({
  event,
  locale,
  onOpen,
}: {
  event: LogEvent;
  locale: string;
  onOpen: () => void;
}) {
  const extra = logHasExtra(event);
  const Icon = LEVEL_ICON[event.level];
  return (
    <li>
      <div
        role={extra ? 'button' : undefined}
        tabIndex={extra ? 0 : undefined}
        onClick={extra ? onOpen : undefined}
        onKeyDown={
          extra
            ? (evt) => {
                if (evt.key === 'Enter' || evt.key === ' ') {
                  evt.preventDefault();
                  onOpen();
                }
              }
            : undefined
        }
        className={cn(
          'grid grid-cols-[auto_auto_minmax(0,1fr)] items-start gap-x-2 border-b border-border/60 px-2 py-1.5 last:border-0',
          LEVEL_ROW[event.level],
          extra && 'cursor-pointer hover:brightness-[0.97] dark:hover:brightness-110',
        )}
      >
        <span className="tabular-nums text-muted-foreground">{formatTime(event.ts, locale)}</span>
        <span
          className={cn(
            'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
            LEVEL_BADGE[event.level],
          )}
        >
          <Icon className="size-3" />
          {event.level}
        </span>
        <span className="min-w-0">
          {event.nodeName || event.nodeId ? (
            <span className="mr-2 text-muted-foreground">{event.nodeName ?? event.nodeId}</span>
          ) : null}
          <span
            className={cn(
              'whitespace-pre-wrap break-words',
              event.level === 'error' && 'font-medium text-destructive',
              event.level === 'warn' && 'font-medium',
            )}
          >
            {event.message}
          </span>
        </span>
      </div>
    </li>
  );
}

function LogDetail({
  event,
  onClose,
  locale,
}: {
  event: LogEvent | null;
  onClose: () => void;
  locale: string;
}) {
  const { t } = useTranslation();
  const extra = event ? logHasExtra(event) : false;

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      /* ignore */
    }
  }

  const payloadText =
    event?.payload === undefined
      ? ''
      : typeof event.payload === 'string'
        ? maskText(event.payload)
        : JSON.stringify(maskSecrets(event.payload), null, 2);

  return (
    <DetailOverlay
      open={Boolean(event && extra)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={t('monitoring.log.detailTitle')}
    >
      {event ? (
        <div className="space-y-3 text-sm">
          <p className="text-xs text-muted-foreground">
            {formatTime(event.ts, locale)} · {event.level} · {event.runId}
            {event.nodeId ? ` · ${event.nodeId}` : ''}
          </p>
          <div>
            <p className="text-xs text-muted-foreground">{t('monitoring.log.message')}</p>
            <p className="whitespace-pre-wrap break-words font-mono text-xs">{event.message}</p>
            <Button type="button" size="sm" variant="ghost" className="mt-1 h-7 px-2" onClick={() => void copy(event.message)}>
              {t('monitoring.log.copyLine')}
            </Button>
          </div>
          {payloadText ? (
            <div>
              <p className="text-xs text-muted-foreground">{t('monitoring.log.payload')}</p>
              <pre className="overflow-auto rounded-md bg-muted p-2 font-mono text-xs">{payloadText}</pre>
              <Button type="button" size="sm" variant="ghost" className="mt-1 h-7 px-2" onClick={() => void copy(payloadText)}>
                {t('monitoring.log.copyPayload')}
              </Button>
            </div>
          ) : null}
          {event.stack ? (
            <div>
              <p className="text-xs text-muted-foreground">{t('monitoring.log.stack')}</p>
              <pre className="overflow-auto rounded-md bg-muted p-2 font-mono text-xs">{event.stack}</pre>
            </div>
          ) : null}
        </div>
      ) : null}
    </DetailOverlay>
  );
}
