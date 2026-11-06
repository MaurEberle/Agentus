import { useEffect } from 'react';
import { createMockHandle } from '@/modules/monitoring/live/mock';
import { createSseHandle } from '@/modules/monitoring/live/sse';
import { parseMockScenario } from '@/modules/monitoring/model/graph';
import type { MonitoringHandle } from '@/modules/monitoring/model/types';
import { applyMonitoringEvent, hydrateLastRun, hydrateMonitoring, useMonitoringStore } from '@/modules/monitoring/store';

let liveHandle: MonitoringHandle | null = null;
let handle: MonitoringHandle | null = null;

function getLiveHandle(): MonitoringHandle {
  if (!liveHandle) liveHandle = createSseHandle();
  return liveHandle;
}

export function getMonitoringHandle(): MonitoringHandle {
  return handle ?? getLiveHandle();
}

export function useLiveRunEvents() {
  useEffect(() => {
    const live = getLiveHandle();
    if (!handle) handle = live;
    hydrateMonitoring(live.getSnapshot());
    if (!live.getSnapshot().run) void hydrateLastRun();
    return live.subscribe(applyMonitoringEvent);
  }, []);
}

export function useLiveMonitoring(mockQuery: string | null) {
  useEffect(() => {
    const scenario = import.meta.env.DEV ? parseMockScenario(mockQuery) : null;
    if (!scenario) return undefined;
    const mock = createMockHandle();
    handle = mock;
    mock.setMockScenario?.(scenario);
    hydrateMonitoring(mock.getSnapshot());
    const stop = mock.subscribe(applyMonitoringEvent);
    return () => {
      stop();
      handle = liveHandle;
    };
  }, [mockQuery]);
}

export async function sendRunChat(text: string): Promise<boolean> {
  useMonitoringStore.getState().setChatGenerating(true);
  const accepted = await getMonitoringHandle().sendChat?.(text);
  if (accepted === false) {
    // Nothing is generating; leaving the flag set would keep the stop button forever.
    useMonitoringStore.getState().setChatGenerating(false);
    return false;
  }
  return true;
}

export function abortRunChat() {
  getMonitoringHandle().abortChat?.();
  useMonitoringStore.getState().setChatGenerating(false);
}

export function setDevScenario(id: Parameters<NonNullable<MonitoringHandle['setMockScenario']>>[0]) {
  getMonitoringHandle().setMockScenario?.(id);
}
