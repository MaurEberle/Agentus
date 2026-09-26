import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import type { ServiceStatus } from '@/store/session';
import { setDevScenario, useLiveMonitoring } from '@/modules/monitoring/live/adapter';
import { hasChatInput } from '@/modules/monitoring/model/graph';
import { formatRunLogMessage } from '@/modules/monitoring/model/logMessage';
import { MOCK_SCENARIOS } from '@/modules/monitoring/model/types';
import { ActivityPanel } from '@/modules/monitoring/activity/ActivityPanel';
import { NetworkChat } from '@/modules/monitoring/chat/NetworkChat';
import { MiniGraph } from '@/modules/monitoring/graph/MiniGraph';
import { LogPanel } from '@/modules/monitoring/log/LogPanel';
import { ResourcesPanel } from '@/modules/monitoring/resources/ResourcesPanel';
import { RunHeader } from '@/modules/monitoring/run-header/RunHeader';
import { useMonitoringStore } from '@/modules/monitoring/store';
import { moduleCardClass, modulePaneHeightClass } from '@/modules/moduleCard';

export function MonitoringModule() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  useLiveMonitoring(params.get('mock'));

  const serviceStatus = useAppStore((state) => state.serviceStatus);
  const activeNetworkName = useAppStore((state) => state.activeNetworkName);
  const activeNetworkId = useAppStore((state) => state.activeNetworkId);
  const run = useMonitoringStore((state) => state.run);
  const resources = useMonitoringStore((state) => state.resources);
  const tab = useMonitoringStore((state) => state.tab);
  const setTab = useMonitoringStore((state) => state.setTab);
  const adapterErrorKey = useMonitoringStore((state) => state.adapterErrorKey);
  const lastErrorMessage = useMonitoringStore((state) => state.lastErrorMessage);
  const setSelectedNodeId = useMonitoringStore((state) => state.setSelectedNodeId);
  const setSelectedLogId = useMonitoringStore((state) => state.setSelectedLogId);
  const clearLogFilter = useMonitoringStore((state) => state.clearLogFilter);

  const chat = hasChatInput(run?.graph);
  const empty = !run;
  const dimmed = serviceStatus === 'disconnected' || serviceStatus === 'stopping';
  const indexingName = indexingNodeName(run);

  useEffect(() => {
    if (!chat && tab === 'chat') setTab('log');
  }, [chat, setTab, tab]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      setSelectedNodeId(null);
      setSelectedLogId(null);
      clearLogFilter();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [clearLogFilter, setSelectedLogId, setSelectedNodeId]);

  return (
    <div className="flex min-h-full w-full min-w-0 flex-col gap-4 p-4 pb-24 [overflow-anchor:none] md:p-6 md:pb-24">
      <h1 className="text-xl font-semibold tracking-tight">{t('monitoring.title')}</h1>
      {import.meta.env.DEV ? <DevBar /> : null}
      <StatusBanner
        status={serviceStatus}
        errorMessage={lastErrorMessage}
        adapterErrorKey={adapterErrorKey}
        indexingName={indexingName}
      />
      {run?.archived ? (
        <Alert>
          <AlertTitle>{t('monitoring.header.lastRun')}</AlertTitle>
          <AlertDescription>{t('monitoring.empty.lastRunBody')}</AlertDescription>
        </Alert>
      ) : null}
      {empty ? (
        <Card className={moduleCardClass}>
          <CardContent className="space-y-2 overflow-y-auto p-6">
            <p className="font-medium">{t('monitoring.empty.stoppedTitle')}</p>
            <p className="text-sm text-muted-foreground">{t('monitoring.empty.stoppedBody')}</p>
            {activeNetworkId ? (
              <p className="text-sm">
                {t('monitoring.empty.stoppedActive', { name: activeNetworkName ?? activeNetworkId })}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">{t('monitoring.empty.stoppedNoNetwork')}</p>
            )}
          </CardContent>
        </Card>
      ) : run ? (
        <>
          <RunHeader run={run} serviceStatus={serviceStatus} />
          {resources || !run.archived ? <ResourcesPanel resources={resources} dimmed={dimmed} /> : null}
          <div className={cn('grid w-full gap-4 md:grid-cols-2 md:items-stretch', modulePaneHeightClass)}>
            <div className="order-2 h-full min-h-0 md:order-1">
              <MiniGraph run={run} dimmed={dimmed} />
            </div>
            <div className="order-1 h-full min-h-0 md:order-2">
              <ActivityPanel run={run} dimmed={dimmed} />
            </div>
          </div>
          <Card className={cn(moduleCardClass, 'min-h-[16rem]')}>
            <div className="flex gap-1 border-b px-2 pt-2" role="tablist" aria-label={t('monitoring.tabs.log')}>
              {chat ? (
                <TabButton active={tab === 'chat'} onClick={() => setTab('chat')}>
                  {t('monitoring.tabs.chat')}
                </TabButton>
              ) : null}
              <TabButton active={tab === 'log' || !chat} onClick={() => setTab('log')}>
                {t('monitoring.tabs.log')}
              </TabButton>
            </div>
            <CardContent className="flex min-h-0 flex-1 flex-col pt-4">
              {chat && tab === 'chat' ? (
                <NetworkChat run={run} serviceStatus={serviceStatus} />
              ) : (
                <LogPanel run={run} />
              )}
            </CardContent>
          </Card>
        </>
      ) : (
        <Card className={moduleCardClass}>
          <CardContent className="overflow-y-auto p-6 text-sm text-muted-foreground">{t('monitoring.empty.stoppedBody')}</CardContent>
        </Card>
      )}
    </div>
  );
}

function TabButton({
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
        active ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
      )}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function indexingNodeName(run: { graph: { nodes: Array<{ id: string; type: string; data: { displayName?: string } }> }; nodesRuntime: Record<string, { waitReason?: string }> } | null) {
  if (!run) return null;
  const id = Object.entries(run.nodesRuntime).find(([, node]) => node.waitReason === 'index')?.[0];
  if (!id) return null;
  const node = run.graph.nodes.find((item) => item.id === id);
  if (!node) return id;
  const name = node.data.displayName?.trim();
  return name || node.type;
}

function StatusBanner({
  status,
  errorMessage,
  adapterErrorKey,
  indexingName,
}: {
  status: ServiceStatus;
  errorMessage: string | null;
  adapterErrorKey: string | null;
  indexingName: string | null;
}) {
  const { t } = useTranslation();
  if (status === 'stopped' || status === 'running') {
    if (adapterErrorKey && status === 'running') {
      return (
        <Alert>
          <AlertTitle>{t(adapterErrorKey)}</AlertTitle>
        </Alert>
      );
    }
    return null;
  }
  if (status === 'disconnected') {
    return (
      <Alert>
        <AlertTitle>{t('monitoring.empty.disconnectedTitle')}</AlertTitle>
        <AlertDescription>{t('monitoring.empty.disconnectedBody')}</AlertDescription>
      </Alert>
    );
  }
  if (status === 'starting') {
    return (
      <Alert>
        <AlertTitle>{t(indexingName ? 'monitoring.empty.indexingTitle' : 'monitoring.empty.startingTitle')}</AlertTitle>
        {indexingName ? <AlertDescription>{t('monitoring.empty.indexingBody', { name: indexingName })}</AlertDescription> : null}
      </Alert>
    );
  }
  if (status === 'stopping') {
    return (
      <Alert>
        <AlertTitle>{t('monitoring.empty.stoppingTitle')}</AlertTitle>
      </Alert>
    );
  }
  return (
    <Alert variant="destructive">
      <AlertTitle>{t('monitoring.empty.errorTitle')}</AlertTitle>
      {errorMessage ? <AlertDescription>{formatRunLogMessage(errorMessage, t)}</AlertDescription> : null}
    </Alert>
  );
}

function DevBar() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const current = params.get('mock');
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-dashed p-2">
      <span className="text-xs text-muted-foreground">{t('monitoring.dev.label')}</span>
      {MOCK_SCENARIOS.map((id) => (
        <Button
          key={id}
          type="button"
          size="sm"
          variant={current === id ? 'default' : 'outline'}
          onClick={() => {
            setDevScenario(id);
            setParams({ mock: id }, { replace: true });
          }}
        >
          {t(`monitoring.dev.${id}`)}
        </Button>
      ))}
    </div>
  );
}
