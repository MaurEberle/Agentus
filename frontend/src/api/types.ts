import type { ServiceStatus } from '@/store/session';

export interface SessionDto {
  activeNetworkId: string | null;
  activeNetworkName?: string;
  serviceStatus: ServiceStatus;
  runId?: string;
  startedAt?: string;
}

export interface NetworkOption {
  id: string;
  name: string;
}

export interface StartRunResponse {
  serviceStatus: ServiceStatus;
  runId: string;
}

export interface StopRunResponse {
  serviceStatus: ServiceStatus;
}
