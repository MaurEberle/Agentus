import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, apiFetch, queryClient, USE_MOCKS } from '@/api/client';
import {
  mockGetSession,
  mockListNetworks,
  mockSetActiveNetwork,
  mockStartRun,
  mockStopRun,
} from '@/api/mocks';
import type { NetworkOption, SessionDto, StartRunResponse, StopRunResponse } from '@/api/types';
import { notify } from '@/lib/notifications';
import { useAppStore } from '@/store';
import type { ServiceStatus } from '@/store/session';

const BUSY: ServiceStatus[] = ['starting', 'running', 'stopping'];

export async function getSession(): Promise<SessionDto> {
  if (USE_MOCKS) return mockGetSession();
  return apiFetch<SessionDto>('/session');
}

export async function listNetworks(): Promise<{ items: NetworkOption[] }> {
  if (USE_MOCKS) return mockListNetworks();
  return apiFetch<{ items: NetworkOption[] }>('/networks');
}

export async function selectActiveNetwork(networkId: string | null) {
  const session = USE_MOCKS
    ? await mockSetActiveNetwork(networkId)
    : await apiFetch<SessionDto>('/session/active-network', {
        method: 'PUT',
        body: JSON.stringify({ networkId }),
      });

  useAppStore.getState().hydrateSession(session);
  void queryClient.invalidateQueries({ queryKey: ['session'] });

  if (session.activeNetworkId) {
    notify({
      titleKey: 'notify.networkSelected.title',
      descriptionKey: 'notify.networkSelected.desc',
      values: { name: session.activeNetworkName ?? session.activeNetworkId },
      variant: 'success',
    });
  } else {
    notify({
      titleKey: 'notify.networkCleared.title',
      descriptionKey: 'notify.networkCleared.desc',
      variant: 'info',
    });
  }
}

export async function startActiveRun() {
  const store = useAppStore.getState();
  if (!store.activeNetworkId) {
    notify({
      titleKey: 'notify.noNetwork.title',
      descriptionKey: 'notify.noNetwork.desc',
      variant: 'warning',
    });
    return;
  }
  if (BUSY.includes(store.serviceStatus)) {
    notify({
      titleKey: 'notify.runConflict.title',
      descriptionKey: 'notify.runConflict.desc',
      variant: 'error',
    });
    return;
  }

  store.setServiceStatus('starting');
  notify({
    titleKey: 'notify.runStarting.title',
    descriptionKey: 'notify.runStarting.desc',
    variant: 'info',
  });

  try {
    const result: StartRunResponse = USE_MOCKS
      ? await mockStartRun()
      : await apiFetch<StartRunResponse>('/run/start', { method: 'POST' });
    store.setServiceStatus(result.serviceStatus);
    store.setRunId(result.runId);
    notify({
      titleKey: 'notify.runRunning.title',
      descriptionKey: 'notify.runRunning.desc',
      values: { name: store.activeNetworkName ?? store.activeNetworkId ?? '' },
      variant: 'success',
    });
    void queryClient.invalidateQueries({ queryKey: ['session'] });
  } catch (error) {
    store.setServiceStatus('error');
    if (error instanceof ApiError && error.status === 409) {
      notify({
        titleKey: 'notify.runConflict.title',
        descriptionKey: 'notify.runConflict.desc',
        variant: 'error',
      });
      return;
    }
    notify({
      titleKey: 'notify.runError.title',
      descriptionKey: 'notify.runError.desc',
      variant: 'error',
    });
  }
}

export async function stopActiveRun() {
  const store = useAppStore.getState();
  if (store.serviceStatus === 'stopped' || store.serviceStatus === 'disconnected') {
    return;
  }

  store.setServiceStatus('stopping');
  notify({
    titleKey: 'notify.runStopping.title',
    descriptionKey: 'notify.runStopping.desc',
    variant: 'info',
  });

  try {
    const result: StopRunResponse = USE_MOCKS
      ? await mockStopRun()
      : await apiFetch<StopRunResponse>('/run/stop', { method: 'POST' });
    store.setServiceStatus(result.serviceStatus);
    store.setRunId(null);
    notify({
      titleKey: 'notify.runStopped.title',
      descriptionKey: 'notify.runStopped.desc',
      variant: 'success',
    });
    void queryClient.invalidateQueries({ queryKey: ['session'] });
  } catch {
    store.setServiceStatus('error');
    notify({
      titleKey: 'notify.runError.title',
      descriptionKey: 'notify.runError.desc',
      variant: 'error',
    });
  }
}

export function useHydrateSession() {
  const hydrateSession = useAppStore((state) => state.hydrateSession);
  const { data } = useQuery({
    queryKey: ['session'],
    queryFn: getSession,
  });

  useEffect(() => {
    if (data) hydrateSession(data);
  }, [data, hydrateSession]);
}

export function useNetworkOptions() {
  return useQuery({
    queryKey: ['networks'],
    queryFn: listNetworks,
  });
}
