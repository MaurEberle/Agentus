import { Copy, Download } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { ArchiveLog } from '@/modules/history/log/ArchiveLog';
import { formatChatBody, formatRunLogMessage } from '@/modules/monitoring/model/logMessage';
import { RunGraph } from '@/modules/history/detail/RunGraph';
import {
  durationMs,
  formatDateTime,
  formatDuration,
  outcomeBadgeVariant,
  shortId,
} from '@/modules/history/model/format';
import type { DetailTab, LogEvent, RunDetail } from '@/modules/history/model/types';
import { useHistoryUi } from '@/modules/history/store';

export function RunDetailPanel({
  detail,
  logs,
  loading,
  missing,
  onExport,
}: {
  detail: RunDetail | null;
  logs: LogEvent[];
  loading: boolean;
  missing: boolean;
  onExport: () => void;
}) {
  const { t, i18n } = useTranslation();
  const tab = useHistoryUi((state) => state.detailTab);
  const setDetailTab = useHistoryUi((state) => state.setDetailTab);

  if (loading) {
    return (
      <div className="space-y-2 p-3">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (missing) {
    return <p className="p-4 text-sm text-muted-foreground">{t('history.detail.missing')}</p>;
  }
  if (!detail) {
    return <p className="p-4 text-sm text-muted-foreground">{t('history.detail.none')}</p>;
  }

  const duration = durationMs(detail.startedAt, detail.endedAt);
  const hasChat = Boolean(detail.chat && detail.chat.length > 0);
  const activeTab: DetailTab = tab === 'chat' && !hasChat ? 'log' : tab;

  return (
    <div className="flex min-h-0 flex-col gap-3 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-semibold">{detail.networkName}</p>
          <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono">{shortId(detail.runId)}</span>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="size-6"
              onClick={() => void navigator.clipboard.writeText(detail.runId)}
            >
              <Copy className="size-3" />
              <span className="sr-only">{t('history.copy')}</span>
            </Button>
            <Badge variant={outcomeBadgeVariant(detail.outcome)}>{t(`history.outcome.${detail.outcome}`)}</Badge>
          </p>
          <p className="text-xs text-muted-foreground">
            {formatDateTime(detail.startedAt, i18n.language)}
            {detail.endedAt ? ` – ${formatDateTime(detail.endedAt, i18n.language)}` : ''}
            {duration !== null ? ` · ${formatDuration(duration)}` : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {detail.outcome === 'running' ? (
            <Button asChild size="sm">
              <Link to="/monitoring">{t('history.list.live')}</Link>
            </Button>
          ) : null}
          <Button type="button" size="sm" variant="outline" onClick={onExport}>
            <Download className="size-3.5" />
            {t('history.detail.exportLog')}
          </Button>
        </div>
      </div>
      {detail.errorMessage && (detail.outcome === 'failed' || detail.outcome === 'timeout') ? (
        <Alert variant="destructive">
          <AlertTitle>{t('history.detail.error')}</AlertTitle>
          <AlertDescription>{formatRunLogMessage(detail.errorMessage, t)}</AlertDescription>
        </Alert>
      ) : null}
      {detail.graphSnapshot ? <RunGraph graph={detail.graphSnapshot} steps={detail.steps} /> : null}
      <div className="flex gap-1 border-b" role="tablist">
        <TabBtn active={activeTab === 'log'} onClick={() => setDetailTab('log')}>
          {t('history.detail.tabLog')}
        </TabBtn>
        <TabBtn active={activeTab === 'steps'} onClick={() => setDetailTab('steps')}>
          {t('history.detail.tabSteps')}
        </TabBtn>
        {hasChat ? (
          <TabBtn active={activeTab === 'chat'} onClick={() => setDetailTab('chat')}>
            {t('history.detail.tabChat')}
          </TabBtn>
        ) : null}
      </div>
      {activeTab === 'log' ? <ArchiveLog logs={logs} detail={detail} /> : null}
      {activeTab === 'steps' ? <StepsCalls detail={detail} /> : null}
      {activeTab === 'chat' && hasChat ? <ChatTranscript detail={detail} /> : null}
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      className={cn(
        'rounded-t-md px-3 py-2 text-sm font-medium',
        active ? 'bg-background text-foreground' : 'text-muted-foreground hover:text-foreground',
      )}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function StepsCalls({ detail }: { detail: RunDetail }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      {detail.steps && detail.steps.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('history.steps.node')}</TableHead>
              <TableHead>{t('history.steps.role')}</TableHead>
              <TableHead>{t('history.steps.status')}</TableHead>
              <TableHead>{t('history.steps.error')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {detail.steps.map((step) => (
              <TableRow key={step.nodeId}>
                <TableCell>{step.nodeName ?? step.nodeId}</TableCell>
                <TableCell>{step.role ?? step.type ?? '—'}</TableCell>
                <TableCell>{t(`history.nodeStatus.${step.status}`)}</TableCell>
                <TableCell className="text-xs text-destructive">
                  {step.errorMessage ? formatRunLogMessage(step.errorMessage, t) : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="text-sm text-muted-foreground">{t('history.steps.empty')}</p>
      )}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('history.table.model')}</TableHead>
            <TableHead>{t('history.table.provider')}</TableHead>
            <TableHead>{t('history.calls.ok')}</TableHead>
            <TableHead>{t('history.table.median')}</TableHead>
            <TableHead>{t('history.table.tokensIn')}</TableHead>
            <TableHead>{t('history.table.tokensOut')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {detail.calls.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-muted-foreground">
                {t('history.calls.empty')}
              </TableCell>
            </TableRow>
          ) : (
            detail.calls.map((call) => (
              <TableRow key={call.id}>
                <TableCell className="font-mono text-xs">{call.model}</TableCell>
                <TableCell>{t(`history.provider.${call.provider}`)}</TableCell>
                <TableCell>{call.ok ? t('history.calls.yes') : t('history.calls.no')}</TableCell>
                <TableCell className="tabular-nums">
                  {call.durationMs !== undefined ? formatDuration(call.durationMs) : '—'}
                </TableCell>
                <TableCell className="tabular-nums">{call.tokensIn ?? '—'}</TableCell>
                <TableCell className="tabular-nums">{call.tokensOut ?? '—'}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}

function ChatTranscript({ detail }: { detail: RunDetail }) {
  const { t, i18n } = useTranslation();
  return (
    <div className="space-y-2">
      {detail.chat?.map((message) => (
        <article
          key={message.id}
          className={cn('flex flex-col gap-1', message.role === 'user' ? 'items-end' : 'items-start')}
        >
          <div
            className={cn(
              'max-w-[92%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm',
              message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted',
            )}
          >
            {formatChatBody(message, t)}
          </div>
          <time className="text-[11px] text-muted-foreground">
            {formatDateTime(message.createdAt, i18n.language)}
          </time>
        </article>
      ))}
    </div>
  );
}
