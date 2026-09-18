import type { NetworkOption, SessionDto } from '@/api/types';
import { mockListEditorNetworks } from '@/modules/network/mocks';
import type { ServiceStatus } from '@/store/session';

const mockSession: SessionDto = {
  activeNetworkId: 'net-demo',
  activeNetworkName: 'Demo-Netz',
  serviceStatus: 'stopped',
};

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function peekMockSession(): SessionDto {
  return { ...mockSession };
}

export async function mockGetSession(): Promise<SessionDto> {
  await delay(40);
  return { ...mockSession };
}

export async function mockListNetworks(): Promise<{ items: NetworkOption[] }> {
  const { items } = await mockListEditorNetworks();
  return { items: items.map((item) => ({ id: item.id, name: item.name })) };
}

export async function mockSetActiveNetwork(networkId: string | null): Promise<SessionDto> {
  await delay(40);
  if (!networkId) {
    mockSession.activeNetworkId = null;
    mockSession.activeNetworkName = undefined;
    return { ...mockSession };
  }
  const { items } = await mockListEditorNetworks();
  const network = items.find((item) => item.id === networkId);
  if (!network) {
    const error = new Error('missing') as Error & { status: number; messageKey: string };
    error.status = 404;
    error.messageKey = 'networks.error.missing';
    throw error;
  }
  mockSession.activeNetworkId = network.id;
  mockSession.activeNetworkName = network.name;
  return { ...mockSession };
}

export async function mockStartRun(): Promise<{ serviceStatus: ServiceStatus; runId: string }> {
  if (!mockSession.activeNetworkId) {
    const error = new Error('no network') as Error & { status: number; messageKey: string };
    error.status = 400;
    error.messageKey = 'notify.noNetwork.title';
    throw error;
  }
  if (
    mockSession.serviceStatus === 'starting' ||
    mockSession.serviceStatus === 'running' ||
    mockSession.serviceStatus === 'stopping'
  ) {
    const error = new Error('busy') as Error & { status: number; messageKey: string };
    error.status = 409;
    error.messageKey = 'notify.runConflict.title';
    throw error;
  }
  mockSession.serviceStatus = 'starting';
  await delay(500);
  mockSession.serviceStatus = 'running';
  mockSession.runId = crypto.randomUUID();
  mockSession.startedAt = new Date().toISOString();
  return { serviceStatus: mockSession.serviceStatus, runId: mockSession.runId };
}

export async function mockStopRun(): Promise<{ serviceStatus: ServiceStatus }> {
  mockSession.serviceStatus = 'stopping';
  await delay(350);
  mockSession.serviceStatus = 'stopped';
  mockSession.runId = undefined;
  mockSession.startedAt = undefined;
  return { serviceStatus: mockSession.serviceStatus };
}


