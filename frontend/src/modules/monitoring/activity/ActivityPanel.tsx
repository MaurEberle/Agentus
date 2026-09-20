import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { nodeDisplayName } from '@/modules/monitoring/model/graph';
import type { RunSnapshot } from '@/modules/monitoring/model/types';
import { moduleCardBodyClass } from '@/modules/moduleCard';

export function ActivityPanel({ run, dimmed }: { run: RunSnapshot; dimmed?: boolean }) {
  const { t } = useTranslation();
  const current = run.activity.currentNodeIds
    .map((id) => {
      const node = run.graph.nodes.find((item) => item.id === id);
      const runtime = run.nodesRuntime[id];
      if (!node) return null;
      return { id, node, runtime };
    })
    .filter((row): row is NonNullable<typeof row> => row !== null);

  const tokenNode = current
    .map((row) => row.runtime)
    .find((runtime) => runtime?.tokens && (runtime.tokens.in !== undefined || runtime.tokens.out !== undefined));

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
        {tokenNode?.tokens ? (
          <div className="grid grid-cols-2 gap-2 text-xs">
            {tokenNode.tokens.in !== undefined ? (
              <p>
                {t('monitoring.activity.tokensIn')}: <span className="font-mono">{tokenNode.tokens.in}</span>
              </p>
            ) : null}
            {tokenNode.tokens.out !== undefined ? (
              <p>
                {t('monitoring.activity.tokensOut')}: <span className="font-mono">{tokenNode.tokens.out}</span>
              </p>
            ) : null}
            {tokenNode.tokens.perSecond !== undefined ? (
              <p>{t('monitoring.activity.perSecond', { value: Math.round(tokenNode.tokens.perSecond) })}</p>
            ) : null}
            {tokenNode.tokens.contextUsed !== undefined && tokenNode.tokens.contextMax !== undefined ? (
              <p>
                {t('monitoring.activity.context', {
                  used: tokenNode.tokens.contextUsed,
                  max: tokenNode.tokens.contextMax,
                })}
              </p>
            ) : null}
          </div>
        ) : null}
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
      </CardContent>
    </Card>
  );
}
