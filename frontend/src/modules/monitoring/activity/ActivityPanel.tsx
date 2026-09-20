import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { nodeDisplayName, runTokenStats } from '@/modules/monitoring/model/graph';
import type { RunSnapshot } from '@/modules/monitoring/model/types';
import { moduleCardBodyClass } from '@/modules/moduleCard';

export function ActivityPanel({ run, dimmed }: { run: RunSnapshot; dimmed?: boolean }) {
  const { t, i18n } = useTranslation();
  const current = run.activity.currentNodeIds
    .map((id) => {
      const node = run.graph.nodes.find((item) => item.id === id);
      const runtime = run.nodesRuntime[id];
      if (!node) return null;
      return { id, node, runtime };
    })
    .filter((row): row is NonNullable<typeof row> => row !== null);

  const tokens = runTokenStats(run);
  const dag = run.activity.dag && run.activity.dag.total > 0 ? run.activity.dag : null;
  const stepError = run.activity.stepError;
  const errorNode = stepError ? run.graph.nodes.find((item) => item.id === stepError.nodeId) : null;

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
          <p className="text-xs font-medium text-muted-foreground">{t('monitoring.activity.current')}</p>
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
        </div>
        {dag ? (
          <div>
            <p className="font-medium">{t('monitoring.activity.dag', { completed: dag.completed, total: dag.total })}</p>
            {dag.pendingNodeIds.length > 0 ? (
              <p className="mt-1 text-xs text-muted-foreground">
                {t('monitoring.activity.pending')}:{' '}
                {dag.pendingNodeIds
                  .map((id) => {
                    const node = run.graph.nodes.find((item) => item.id === id);
                    return node ? nodeDisplayName(node) : id;
                  })
                  .join(', ')}
              </p>
            ) : null}
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
