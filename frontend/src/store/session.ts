import type { StateCreator } from 'zustand';
import type { AppStore } from '@/store/types';

export type ServiceStatus =
  | 'disconnected'
  | 'stopped'
  | 'starting'
  | 'running'
  | 'stopping'
  | 'error';

export interface SessionSnapshot {
  activeNetworkId: string | null;
  activeNetworkName?: string;
  serviceStatus: ServiceStatus;
  runId?: string;
  phase?: string | null;
  phaseLabel?: string | null;
}

export interface SessionSlice {
  activeNetworkId: string | null;
  activeNetworkName: string | null;
  serviceStatus: ServiceStatus;
  runId: string | null;
  phase: string | null;
  phaseLabel: string | null;
  setActiveNetwork: (id: string | null, name?: string | null) => void;
  setServiceStatus: (status: ServiceStatus) => void;
  setRunId: (id: string | null) => void;
  hydrateSession: (session: SessionSnapshot) => void;
}

export const createSessionSlice: StateCreator<AppStore, [], [], SessionSlice> = (set) => ({
  activeNetworkId: null,
  activeNetworkName: null,
  serviceStatus: 'stopped',
  runId: null,
  phase: null,
  phaseLabel: null,
  setActiveNetwork: (id, name = null) =>
    set({ activeNetworkId: id, activeNetworkName: name ?? null }),
  setServiceStatus: (serviceStatus) =>
    set({
      serviceStatus,
      ...(serviceStatus === 'starting' ? {} : { phase: null, phaseLabel: null }),
    }),
  setRunId: (runId) => set({ runId }),
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
