import { QueryClient } from '@tanstack/react-query';

export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export type ApiUsage = { kind: string; network?: string; node?: string };

export class ApiError extends Error {
  status: number;
  messageKey?: string;
  usages?: ApiUsage[];
  loaded?: boolean;

  constructor(
    status: number,
    messageKey?: string,
    message?: string,
    extra?: { usages?: ApiUsage[]; loaded?: boolean },
  ) {
    super(message ?? messageKey ?? `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.messageKey = messageKey;
    this.usages = extra?.usages;
    this.loaded = extra?.loaded;
  }
}

interface ErrorBody {
  messageKey?: string;
  message?: string;
  usages?: ApiUsage[];
  loaded?: boolean;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith('http')
    ? path
    : `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;

  const headers = new Headers(init?.headers);
  if (!headers.has('Content-Type') && init?.body) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, { ...init, headers });
  if (!response.ok) {
    let body: ErrorBody | undefined;
    try {
      body = (await response.json()) as ErrorBody;
    } catch {
      body = undefined;
    }
    throw new ApiError(response.status, body?.messageKey, body?.message, {
      usages: body?.usages,
      loaded: body?.loaded,
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
