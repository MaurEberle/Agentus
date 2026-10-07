import type { StateCreator } from 'zustand';
import type { AppStore } from '@/store/types';

export type ServiceStatus =
  | 'disconnected'
  | 'stopped'
  | 'starting'
  | 'running'
  | 'stopping'
  | 'error';

export interface WaitAsk {
  id: string;
  speaker: string;
  excerpt: string;
  nodeId?: string;
}

export interface SessionSnapshot {
  activeNetworkId: string | null;
  activeNetworkName?: string;
  serviceStatus: ServiceStatus;
  runId?: string;
  phase?: string | null;
  phaseLabel?: string | null;
  waitAsk?: WaitAsk | null;
}

export interface SessionSlice {
  activeNetworkId: string | null;
  activeNetworkName: string | null;
  serviceStatus: ServiceStatus;
  runId: string | null;
  phase: string | null;
  phaseLabel: string | null;
  waitAsk: WaitAsk | null;
  setActiveNetwork: (id: string | null, name?: string | null) => void;
  setServiceStatus: (status: ServiceStatus) => void;
  setRunId: (id: string | null) => void;
  setWaitAsk: (ask: WaitAsk | null) => void;
  hydrateSession: (session: SessionSnapshot) => void;
}

export const createSessionSlice: StateCreator<AppStore, [], [], SessionSlice> = (set) => ({
  activeNetworkId: null,
  activeNetworkName: null,
  serviceStatus: 'stopped',
  runId: null,
  phase: null,
  phaseLabel: null,
  waitAsk: null,
  setActiveNetwork: (id, name = null) =>
    set({ activeNetworkId: id, activeNetworkName: name ?? null }),
  setServiceStatus: (serviceStatus) =>
    set({
      serviceStatus,
      ...(serviceStatus === 'starting' ? {} : { phase: null, phaseLabel: null }),
    }),
  setRunId: (runId) => set({ runId }),
  setWaitAsk: (waitAsk) => set({ waitAsk }),
  hydrateSession: (session) =>
    set({
      activeNetworkId: session.activeNetworkId,
      activeNetworkName: session.activeNetworkName ?? null,
      serviceStatus: session.serviceStatus,
      runId: session.runId ?? null,
      phase: session.phase ?? null,
      phaseLabel: session.phaseLabel ?? null,
    }),
});
