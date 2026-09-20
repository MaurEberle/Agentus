import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, apiFetch, queryClient } from '@/api/client';
import type { NetworkOption, SessionDto, StartRunResponse, StopRunResponse } from '@/api/types';
import { notify } from '@/lib/notifications';
import { listNetworkSummaries } from '@/modules/dashboard/api';
import { useAppStore } from '@/store';
import type { ServiceStatus } from '@/store/session';

const BUSY: ServiceStatus[] = ['starting', 'running', 'stopping'];

export async function getSession(): Promise<SessionDto> {
  return apiFetch<SessionDto>('/session');
}

export async function listNetworks(): Promise<{ items: NetworkOption[] }> {
  return listNetworkSummaries();
}

export async function selectActiveNetwork(networkId: string | null) {
  const session = await apiFetch<SessionDto>('/session/active-network', {
    method: 'PUT',
    body: JSON.stringify({ networkId }),
  });

  useAppStore.getState().hydrateSession(session);
  void queryClient.invalidateQueries({ queryKey: ['session'] });
  void queryClient.invalidateQueries({ queryKey: ['networks'] });

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
    const result: StartRunResponse = await apiFetch<StartRunResponse>('/run/start', { method: 'POST' });
    store.setServiceStatus(result.serviceStatus);
    store.setRunId(result.runId);
    notify({
      titleKey: 'notify.runRunning.title',
      descriptionKey: 'notify.runRunning.desc',
      values: { name: store.activeNetworkName ?? store.activeNetworkId ?? '' },
      variant: 'success',
    });
    void queryClient.invalidateQueries({ queryKey: ['session'] });
    void queryClient.invalidateQueries({ queryKey: ['runs'] });
    void queryClient.invalidateQueries({ queryKey: ['networks'] });
    void queryClient.invalidateQueries({ queryKey: ['help-chat', 'status'] });
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
    const result: StopRunResponse = await apiFetch<StopRunResponse>('/run/stop', { method: 'POST' });
    store.setServiceStatus(result.serviceStatus);
    store.setRunId(null);
    notify({
      titleKey: 'notify.runStopped.title',
      descriptionKey: 'notify.runStopped.desc',
      variant: 'success',
    });
    void queryClient.invalidateQueries({ queryKey: ['session'] });
    void queryClient.invalidateQueries({ queryKey: ['runs'] });
    void queryClient.invalidateQueries({ queryKey: ['networks'] });
    void queryClient.invalidateQueries({ queryKey: ['help-chat', 'status'] });
  } catch {
    store.setServiceStatus('error');
    notify({
      titleKey: 'notify.runError.title',
      descriptionKey: 'notify.runError.desc',
      variant: 'error',
    });
  }
}

export function useSessionQuery() {
  return useQuery({
    queryKey: ['session'],
    queryFn: getSession,
  });
}

export function useHydrateSession() {
  const hydrateSession = useAppStore((state) => state.hydrateSession);
  const { data } = useSessionQuery();

  useEffect(() => {
    if (data) hydrateSession(data);
  }, [data, hydrateSession]);
}

export function useNetworkOptions() {
  return useQuery({
    queryKey: ['networks'],
    queryFn: listNetworkSummaries,
  });
}
