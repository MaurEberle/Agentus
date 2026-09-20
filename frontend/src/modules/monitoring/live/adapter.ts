import { useEffect } from 'react';
import { createMockHandle } from '@/modules/monitoring/live/mock';
import { createSseHandle } from '@/modules/monitoring/live/sse';
import { parseMockScenario } from '@/modules/monitoring/model/graph';
import type { MonitoringHandle } from '@/modules/monitoring/model/types';
import { applyMonitoringEvent, hydrateLastRun, hydrateMonitoring, useMonitoringStore } from '@/modules/monitoring/store';

let handle: MonitoringHandle | null = null;

export function getMonitoringHandle(): MonitoringHandle {
  if (!handle) {
    handle = createSseHandle();
  }
  return handle;
}

export function useLiveMonitoring(mockQuery: string | null) {
  useEffect(() => {
    const scenario = import.meta.env.DEV ? parseMockScenario(mockQuery) : null;
    handle = scenario ? createMockHandle() : createSseHandle();
    if (scenario) handle.setMockScenario?.(scenario);
    hydrateMonitoring(handle.getSnapshot());
    if (!scenario && !handle.getSnapshot().run) void hydrateLastRun();
    const stop = handle.subscribe(applyMonitoringEvent);
    return () => {
      stop();
      handle = null;
    };
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
