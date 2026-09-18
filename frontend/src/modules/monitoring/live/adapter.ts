import { useEffect } from 'react';
import { USE_MOCKS } from '@/api/client';
import { createMockHandle } from '@/modules/monitoring/live/mock';
import { createSseHandle } from '@/modules/monitoring/live/sse';
import { parseMockScenario } from '@/modules/monitoring/model/graph';
import type { MonitoringHandle } from '@/modules/monitoring/model/types';
import { applyMonitoringEvent, hydrateMonitoring, useMonitoringStore } from '@/modules/monitoring/store';

let handle: MonitoringHandle | null = null;

export function getMonitoringHandle(): MonitoringHandle {
  if (!handle) {
    handle = USE_MOCKS ? createMockHandle() : createSseHandle();
  }
  return handle;
}

export function useLiveMonitoring(mockQuery: string | null) {
  useEffect(() => {
    const live = getMonitoringHandle();
    const scenario = parseMockScenario(mockQuery);
    if (scenario && live.setMockScenario) live.setMockScenario(scenario);
    hydrateMonitoring(live.getSnapshot());
    const stop = live.subscribe(applyMonitoringEvent);
    return stop;
  }, [mockQuery]);
}

export function sendRunChat(text: string) {
  getMonitoringHandle().sendChat?.(text);
  useMonitoringStore.getState().setChatGenerating(true);
}

export function abortRunChat() {
  getMonitoringHandle().abortChat?.();
  useMonitoringStore.getState().setChatGenerating(false);
}

export function setDevScenario(id: Parameters<NonNullable<MonitoringHandle['setMockScenario']>>[0]) {
  getMonitoringHandle().setMockScenario?.(id);
}
