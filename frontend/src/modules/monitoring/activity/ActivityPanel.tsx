import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { nodeDisplayName, runTokenStats } from '@/modules/monitoring/model/graph';
import type { RunSnapshot } from '@/modules/monitoring/model/types';
import { moduleCardBodyClass } from '@/modules/moduleCard';

export function ActivityPanel({ run, dimmed }: { run: RunSnapshot; dimmed?: boolean }) {
  const { t, i18n } = useTranslation();
  const currentIds = new Set(run.activity.currentNodeIds);
  for (const [id, runtime] of Object.entries(run.nodesRuntime)) {
    if (runtime.status === 'running' || runtime.status === 'waiting') currentIds.add(id);
  }
  const current = [...currentIds]
    .map((id) => {
      const node = run.graph.nodes.find((item) => item.id === id);
      const runtime = run.nodesRuntime[id];
      if (!node) return null;
      return { id, node, runtime };
    })
    .filter((row): row is NonNullable<typeof row> => row !== null);

  const agents = run.graph.nodes.filter((node) => node.type === 'agent');
  const agentsDone = agents.filter((node) => run.nodesRuntime[node.id]?.status === 'done').length;
  const tokens = runTokenStats(run);
  const stepError = run.activity.stepError;
  const errorNode = stepError ? run.graph.nodes.find((item) => item.id === stepError.nodeId) : null;
  const task = current
    .map((row) => row.runtime?.lastMessage)
    .find((text) => Boolean(text && text.trim()));

  return (
    <Card className={cn('flex h-full min-h-0 flex-col overflow-hidden', dimmed && 'opacity-60')}>
      <CardHeader className="pb-2">
        <CardTitle>{t('monitoring.activity.title')}</CardTitle>
      </CardHeader>
      <CardContent className={cn(moduleCardBodyClass, 'flex flex-col gap-3 text-sm')}>
        {stepError ? (
          <Alert variant="destructive">
            <AlertTitle>{t('monitoring.activity.stepError')}</AlertTitle>
            <AlertDescription>
              {errorNode ? `${nodeDisplayName(errorNode)}: ` : ''}
              {stepError.message}
            </AlertDescription>
          </Alert>
        ) : null}
        <div>
          <p className="text-xs font-medium text-muted-foreground">{t('monitoring.activity.now')}</p>
          {current.length === 0 ? (
            <p className="mt-1 text-muted-foreground">{t('monitoring.activity.none')}</p>
          ) : (
            <ul className="mt-1 space-y-1">
              {current.map(({ id, node, runtime }) => (
                <li key={id} className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{nodeDisplayName(node)}</span>
                  {runtime ? (
                    <span className="text-xs text-muted-foreground">
                      {t(`monitoring.nodeStatus.${runtime.status}`)}
                      {runtime.waitReason && runtime.waitReason !== 'none'
                        ? ` · ${t(`monitoring.wait.${runtime.waitReason}`)}`
                        : ''}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {task ? (
            <p className="mt-2 text-sm leading-snug">
              <span className="text-xs font-medium text-muted-foreground">{t('monitoring.activity.task')}: </span>
              {task}
            </p>
          ) : null}
        </div>
        {agents.length > 0 ? (
          <div>
            <p className="text-xs font-medium text-muted-foreground">{t('monitoring.activity.agents')}</p>
            <p className="mt-1 font-medium">
              {t('monitoring.activity.agentsDone', { completed: agentsDone, total: agents.length })}
            </p>
            <ul className="mt-1 space-y-1">
              {agents.map((node) => {
                const runtime = run.nodesRuntime[node.id];
                const status = runtime?.status ?? 'idle';
                return (
                  <li key={node.id} className="flex flex-wrap items-center gap-2">
                    <span>{nodeDisplayName(node)}</span>
                    <span className="text-xs text-muted-foreground">
                      {t(`monitoring.nodeStatus.${status}`)}
                      {runtime?.waitReason && runtime.waitReason !== 'none' && status !== 'idle'
                        ? ` · ${t(`monitoring.wait.${runtime.waitReason}`)}`
                        : ''}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
        <div className="mt-auto grid grid-cols-2 gap-3 border-t pt-3">
          <div>
            <p className="text-xs font-medium text-muted-foreground">{t('monitoring.activity.rate')}</p>
            <p className="font-mono text-lg tabular-nums">
              {tokens.perSecond !== undefined ? Math.round(tokens.perSecond) : '—'}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">{t('monitoring.activity.runTotal')}</p>
            <p className="font-mono text-lg tabular-nums">
              {new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 0 }).format(tokens.out)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
