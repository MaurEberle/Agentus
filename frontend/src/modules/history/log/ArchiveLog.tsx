import { useMemo } from 'react';
import { AlertTriangle, Bug, Info, OctagonAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
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
import { filterLogs, logHasExtra } from '@/modules/monitoring/model/graph';
import { formatRunLogMessage } from '@/modules/monitoring/model/logMessage';
import { maskSecrets, maskText } from '@/modules/monitoring/model/mask';
import { DetailOverlay } from '@/modules/monitoring/overlay/DetailOverlay';
import { formatTime } from '@/modules/history/model/format';
import type { LogEvent, LogLevel, RunDetail } from '@/modules/history/model/types';
import { LOG_LEVELS } from '@/modules/history/model/types';
import { useHistoryUi } from '@/modules/history/store';

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

export function ArchiveLog({ logs, detail }: { logs: LogEvent[]; detail: RunDetail }) {
  const { t, i18n } = useTranslation();
  const levelMin = useHistoryUi((state) => state.logLevelMin);
  const query = useHistoryUi((state) => state.logQuery);
  const nodeId = useHistoryUi((state) => state.logNodeId);
  const errorsOnly = useHistoryUi((state) => state.logErrorsOnly);
  const selectedLogId = useHistoryUi((state) => state.selectedLogId);
  const setLogLevelMin = useHistoryUi((state) => state.setLogLevelMin);
  const setLogQuery = useHistoryUi((state) => state.setLogQuery);
  const setLogNodeId = useHistoryUi((state) => state.setLogNodeId);
  const setLogErrorsOnly = useHistoryUi((state) => state.setLogErrorsOnly);
  const setSelectedLogId = useHistoryUi((state) => state.setSelectedLogId);

  const filtered = useMemo(
    () => filterLogs(logs, { levelMin, query, nodeId, errorsOnly }),
    [errorsOnly, levelMin, logs, nodeId, query],
  );
  const visible = useMemo(() => filtered.slice().reverse(), [filtered]);
  const selected = logs.find((item) => item.id === selectedLogId) ?? null;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-32">
          <Label className="text-xs">{t('history.log.level')}</Label>
          <Select value={levelMin} onValueChange={(value) => setLogLevelMin(value as LogLevel)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LOG_LEVELS.map((level) => (
                <SelectItem key={level} value={level}>
                  {t(`history.level.${level}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="min-w-[8rem] flex-1">
          <Label className="text-xs" htmlFor="history-log-q">
            {t('history.log.search')}
          </Label>
          <Input id="history-log-q" value={query} onChange={(event) => setLogQuery(event.target.value)} />
        </div>
        <div className="w-40">
          <Label className="text-xs">{t('history.log.node')}</Label>
          <Select value={nodeId ?? 'all'} onValueChange={(value) => setLogNodeId(value === 'all' ? null : value)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('history.log.allNodes')}</SelectItem>
              {(detail.graphSnapshot
                ? detail.graphSnapshot.nodes.map((node) => ({
                    id: node.id,
                    name:
                      typeof node.data.displayName === 'string' && node.data.displayName.trim()
                        ? node.data.displayName
                        : node.type,
                  }))
                : (detail.steps ?? []).map((step) => ({
                    id: step.nodeId,
                    name: step.nodeName ?? step.nodeId,
                  }))
              ).map((node) => (
                <SelectItem key={node.id} value={node.id}>
                  {node.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <Checkbox checked={errorsOnly} onCheckedChange={(value) => setLogErrorsOnly(value === true)} />
          {t('history.log.errorsOnly')}
        </label>
      </div>
      <div className="max-h-[min(24rem,50vh)] min-h-[10rem] overflow-auto rounded-md border bg-muted/20 font-log text-xs">
        {visible.length === 0 ? (
          <p className="p-3 font-sans text-sm text-muted-foreground">{t('history.log.empty')}</p>
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
  const { t } = useTranslation();
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
          'grid grid-cols-[auto_auto_minmax(0,1fr)] items-start gap-x-2 border-b border-border/60 px-2 py-1.5',
          LEVEL_ROW[event.level],
          extra && 'cursor-pointer',
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
          {event.nodeName ? <span className="mr-2 text-muted-foreground">{event.nodeName}</span> : null}
          <span className={cn(event.level === 'error' && 'font-medium text-destructive')}>
            {formatRunLogMessage(event.message, t, event.payload)}
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
  const messageText = event ? formatRunLogMessage(event.message, t, event.payload) : '';
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
      title={t('history.log.detailTitle')}
    >
      {event ? (
        <div className="space-y-3 font-log text-sm">
          <p className="text-xs text-muted-foreground">
            {formatTime(event.ts, locale)} · {event.level} · {event.runId}
          </p>
          <p className="whitespace-pre-wrap font-log text-xs">{messageText}</p>
          {payloadText ? (
            <pre className="overflow-auto rounded-md bg-muted p-2 font-log text-xs">{payloadText}</pre>
          ) : null}
          {event.stack ? (
            <pre className="overflow-auto rounded-md bg-muted p-2 font-log text-xs">{event.stack}</pre>
          ) : null}
        </div>
      ) : null}
    </DetailOverlay>
  );
}
