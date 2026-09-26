import { useEffect, useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { outcomeBadgeVariant } from '@/modules/history/model/format';
import { formatDateTime, formatDuration, serviceBadgeVariant, shortId } from '@/modules/monitoring/model/format';
import { activeLlms, activeNonLlm } from '@/modules/monitoring/model/graph';
import type { RunSnapshot } from '@/modules/monitoring/model/types';
import { moduleCardBodyClass, moduleCardClass } from '@/modules/moduleCard';
import type { ServiceStatus } from '@/store/session';

function useNow(ms: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const step = reduced ? Math.max(ms, 15_000) : ms;
    const id = window.setInterval(() => setNow(Date.now()), step);
    return () => window.clearInterval(id);
  }, [ms]);
  return now;
}

export function RunHeader({
  run,
  serviceStatus,
}: {
  run: RunSnapshot;
  serviceStatus: ServiceStatus;
}) {
  const { t, i18n } = useTranslation();
  const now = useNow(1000);
  const [copied, setCopied] = useState(false);
  const startMs = Date.parse(run.startedAt);
  const endMs = run.endedAt ? Date.parse(run.endedAt) : run.archived ? startMs : now;
  const duration = formatDuration(Math.max(0, endMs - startMs));
  const llms = activeLlms(run.graph, run.nodesRuntime);
  const others = activeNonLlm(run.graph, run.nodesRuntime);
  const runningCount = Object.values(run.nodesRuntime).filter((node) => node.status === 'running').length;

  async function copyId() {
    try {
      await navigator.clipboard.writeText(run.runId);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  const waitReasons = others
    .map((row) => run.nodesRuntime[row.id]?.waitReason)
    .filter((reason): reason is NonNullable<typeof reason> => Boolean(reason) && reason !== 'none');
  const primaryWait = waitReasons[0];

  return (
    <Card className={moduleCardClass}>
      <CardContent className={`${moduleCardBodyClass} flex flex-col gap-3 p-4`}>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">{run.networkName}</p>
            <p className="text-xs text-muted-foreground">
              {t('monitoring.header.started')}: {formatDateTime(run.startedAt, i18n.language)}
            </p>
          </div>
          {run.archived ? (
            <>
              <Badge variant="secondary">{t('monitoring.header.lastRun')}</Badge>
              {run.outcome ? (
                <Badge variant={outcomeBadgeVariant(run.outcome)}>{t(`history.outcome.${run.outcome}`)}</Badge>
              ) : null}
            </>
          ) : (
            <Badge variant={serviceBadgeVariant(serviceStatus)}>{t(`status.${serviceStatus}`)}</Badge>
          )}
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <span>{t('monitoring.header.runId')}</span>
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">{shortId(run.runId)}</code>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button type="button" size="icon" variant="ghost" className="size-7" onClick={() => void copyId()}>
                  {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                  <span className="sr-only">{t('monitoring.copy')}</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>{copied ? t('monitoring.copied') : t('monitoring.copy')}</TooltipContent>
            </Tooltip>
          </div>
          <p className="text-xs tabular-nums text-muted-foreground">
            {t('monitoring.header.duration')}: {duration}
          </p>
          <p className="text-xs text-muted-foreground">
            {t('monitoring.header.step')}:{' '}
            {runningCount > 0
              ? t('monitoring.header.runningCount', { count: runningCount })
              : primaryWait
                ? t(`monitoring.wait.${primaryWait}`)
                : t('monitoring.activity.none')}
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium text-muted-foreground">{t('monitoring.header.activeLlms')}</p>
          {llms.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('monitoring.header.noLlm')}</p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {llms.map((llm) => {
                if (!llm) return null;
                const node = run.graph.nodes.find((item) => item.id === llm.nodeId);
                const name =
                  (typeof node?.data.displayName === 'string' && node.data.displayName) || llm.nodeId;
                const local = llm.provider === 'ollama';
                return (
                  <li
                    key={`${llm.nodeId}:${llm.model}`}
                    className="flex flex-wrap items-center gap-2 rounded-md border px-2 py-1 text-xs"
                  >
                    <span className="font-medium">{name}</span>
                    <span className="font-mono">{llm.model}</span>
                    <span className="text-muted-foreground">{t(`monitoring.provider.${llm.provider}`)}</span>
                    <Badge variant={local ? 'secondary' : 'outline'}>
                      {local ? t('monitoring.header.local') : t('monitoring.header.cloud')}
                    </Badge>
                  </li>
                );
              })}
            </ul>
          )}
          {others.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              {t('monitoring.header.otherNodes')}:{' '}
              {others
                .map((row) => `${row.name} (${t(`monitoring.nodeStatus.${row.status}`)})`)
                .join(', ')}
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
