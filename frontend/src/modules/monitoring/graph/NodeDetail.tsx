import { useTranslation } from 'react-i18next';
import { DetailOverlay } from '@/modules/monitoring/overlay/DetailOverlay';
import { nodeDisplayName } from '@/modules/monitoring/model/graph';
import type { RunSnapshot } from '@/modules/monitoring/model/types';
import { useMonitoringStore } from '@/modules/monitoring/store';

export function NodeDetail({ run }: { run: RunSnapshot }) {
  const { t } = useTranslation();
  const selectedNodeId = useMonitoringStore((state) => state.selectedNodeId);
  const setSelectedNodeId = useMonitoringStore((state) => state.setSelectedNodeId);
  const node = run.graph.nodes.find((item) => item.id === selectedNodeId);
  const runtime = selectedNodeId ? run.nodesRuntime[selectedNodeId] : undefined;

  return (
    <DetailOverlay
      open={Boolean(selectedNodeId && node)}
      onOpenChange={(open) => {
        if (!open) setSelectedNodeId(null);
      }}
      title={node ? nodeDisplayName(node) : t('monitoring.graph.detailTitle')}
    >
      {node && runtime ? (
        <dl className="space-y-2 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">{t('monitoring.graph.role')}</dt>
            <dd>{runtime.role || t(`monitoring.nodeType.${node.type}`, { defaultValue: node.type })}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">{t('monitoring.graph.status')}</dt>
            <dd>{t(`monitoring.nodeStatus.${runtime.status}`)}</dd>
          </div>
          {runtime.waitReason && runtime.waitReason !== 'none' ? (
            <div>
              <dt className="text-xs text-muted-foreground">{t('monitoring.graph.wait')}</dt>
              <dd>{t(`monitoring.wait.${runtime.waitReason}`)}</dd>
            </div>
          ) : null}
          {runtime.lastMessage ? (
            <div>
              <dt className="text-xs text-muted-foreground">{t('monitoring.graph.lastMessage')}</dt>
              <dd className="max-h-40 overflow-y-auto whitespace-pre-wrap break-words">{runtime.lastMessage}</dd>
            </div>
          ) : null}
          {runtime.error ? (
            <div>
              <dt className="text-xs text-muted-foreground">{t('monitoring.graph.error')}</dt>
              <dd className="text-destructive">{runtime.error}</dd>
            </div>
          ) : null}
          {runtime.llm ? (
            <>
              <div>
                <dt className="text-xs text-muted-foreground">{t('monitoring.graph.model')}</dt>
                <dd className="font-mono">{runtime.llm.model}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">{t('monitoring.graph.provider')}</dt>
                <dd>{t(`monitoring.provider.${runtime.llm.provider}`)}</dd>
              </div>
            </>
          ) : null}
          {runtime.tokens &&
          (runtime.tokens.in !== undefined ||
            runtime.tokens.out !== undefined ||
            runtime.tokens.perSecond !== undefined) ? (
            <div>
              <dt className="text-xs text-muted-foreground">{t('monitoring.graph.tokens')}</dt>
              <dd className="space-y-0.5 font-mono text-xs">
                {runtime.tokens.in !== undefined ? (
                  <p>
                    {t('monitoring.activity.tokensIn')}: {runtime.tokens.in}
                  </p>
                ) : null}
                {runtime.tokens.out !== undefined ? (
                  <p>
                    {t('monitoring.activity.tokensOut')}: {runtime.tokens.out}
                  </p>
                ) : null}
                {runtime.tokens.perSecond !== undefined ? (
                  <p>{t('monitoring.activity.perSecond', { value: Math.round(runtime.tokens.perSecond) })}</p>
                ) : null}
                {runtime.tokens.contextUsed !== undefined && runtime.tokens.contextMax !== undefined ? (
                  <p>
                    {t('monitoring.activity.context', {
                      used: runtime.tokens.contextUsed,
                      max: runtime.tokens.contextMax,
                    })}
                  </p>
                ) : null}
              </dd>
            </div>
          ) : null}
        </dl>
      ) : (
        <p className="text-sm text-muted-foreground">{t('monitoring.activity.none')}</p>
      )}
    </DetailOverlay>
  );
}
