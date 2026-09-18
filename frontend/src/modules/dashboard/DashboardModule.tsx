import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { notify } from '@/lib/notifications';
import { useDashboardQueries } from '@/modules/dashboard/api';
import { ActiveNetworkCard } from '@/modules/dashboard/sections/ActiveNetworkCard';
import { EnvironmentCard } from '@/modules/dashboard/sections/EnvironmentCard';
import { HelpHintCard } from '@/modules/dashboard/sections/HelpHintCard';
import { QuickLinks } from '@/modules/dashboard/sections/QuickLinks';
import { RecentNetworksCard } from '@/modules/dashboard/sections/RecentNetworksCard';
import { RecentRunsCard } from '@/modules/dashboard/sections/RecentRunsCard';
import { SetupCard } from '@/modules/dashboard/sections/SetupCard';
import { StatusCard } from '@/modules/dashboard/sections/StatusCard';
import { WeekStatsCard } from '@/modules/dashboard/sections/WeekStatsCard';
import { useAppStore } from '@/store';

function useErrorToast(active: boolean, titleKey: string) {
  const shown = useRef(false);
  useEffect(() => {
    if (!active) {
      shown.current = false;
      return;
    }
    if (shown.current) return;
    shown.current = true;
    notify({ titleKey, variant: 'error', persist: false });
  }, [active, titleKey]);
}

export function DashboardModule() {
  const { t } = useTranslation();
  const activeNetworkId = useAppStore((state) => state.activeNetworkId);
  const { networks, ping, models, stores, help, historyOk, recentRuns, weekRuns } =
    useDashboardQueries();

  useErrorToast(networks.isError, 'dashboard.error.networks');
  useErrorToast(stores.isError, 'dashboard.error.load');
  useErrorToast(recentRuns.isError, 'dashboard.error.runs');

  const networksLoading = networks.isLoading;
  const activeItem = networks.data?.items.find((item) => item.id === activeNetworkId);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4 pb-24 md:p-6 md:pb-24">
      <h1 className="text-xl font-semibold tracking-tight">{t('dashboard.title')}</h1>
      <StatusCard />
      <HelpHintCard onboardingSeen={help.data?.onboardingSeen} loading={help.isLoading} />
      <SetupCard
        loading={ping.isLoading || help.isLoading || networksLoading}
        ollamaOk={ping.isLoading ? undefined : ping.data?.ok === true}
        helpConfigured={help.isLoading ? undefined : help.data?.configured === true}
        hasNetwork={networksLoading ? undefined : (networks.data?.items.length ?? 0) > 0}
      />
      <div className="grid gap-4 md:grid-cols-2">
        <ActiveNetworkCard loading={networksLoading} item={activeItem} />
        <RecentNetworksCard loading={networksLoading} items={networks.data?.items ?? []} />
        <RecentRunsCard
          loading={stores.isLoading || recentRuns.isLoading}
          storeOk={historyOk}
          items={recentRuns.data?.items ?? []}
        />
        <div className="flex flex-col gap-4">
          <WeekStatsCard
            loading={stores.isLoading || weekRuns.isLoading}
            storeOk={historyOk}
            items={weekRuns.data?.items ?? []}
          />
          <EnvironmentCard
            loading={ping.isLoading || models.isLoading || stores.isLoading || help.isLoading}
            ping={ping.data}
            models={models.data?.items ?? []}
            stores={stores.data}
            help={help.data}
          />
          <QuickLinks />
        </div>
      </div>
    </div>
  );
}
