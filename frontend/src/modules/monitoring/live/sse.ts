import { API_BASE, apiFetch } from '@/api/client';
import type { ServiceStatus } from '@/store/session';
import type {
  ChatMessage,
  MonitoringEvent,
  MonitoringHandle,
  ResourceSnapshot,
  RunSnapshot,
} from '@/modules/monitoring/model/types';

type Snapshot = {
  serviceStatus: ServiceStatus;
  run: RunSnapshot | null;
  resources: ResourceSnapshot | null;
};

function parseEvent(name: string, raw: string): MonitoringEvent | null {
  try {
    const data = JSON.parse(raw) as Record<string, unknown>;
    if (name === 'service') {
      return {
        type: 'service',
        serviceStatus: data.serviceStatus as ServiceStatus,
        errorMessage: typeof data.errorMessage === 'string' ? data.errorMessage : undefined,
      };
    }
    if (name === 'run') {
      return { type: 'run', run: data as Partial<RunSnapshot> };
    }
    if (name === 'resources') {
      return { type: 'resources', resources: data as unknown as ResourceSnapshot };
    }
    if (name === 'log') {
      return { type: 'log', log: data as never };
    }
    if (name === 'chat') {
      return {
        type: 'chat',
        runId: String(data.runId ?? ''),
        message: data.message as ChatMessage | undefined,
        id: typeof data.id === 'string' ? data.id : undefined,
        delta: typeof data.delta === 'string' ? data.delta : undefined,
      };
    }
  } catch {
    return { type: 'adapterError', messageKey: 'monitoring.empty.errorTitle' };
  }
  return null;
}

export function createSseHandle(): MonitoringHandle {
  const listeners = new Set<(evt: MonitoringEvent) => void>();
  const snapshot: Snapshot = { serviceStatus: 'disconnected', run: null, resources: null };
  let source: EventSource | null = null;
  let pollTimer: number | null = null;
  let retry = 1000;
  let reconnectTimer: number | null = null;
  let lastEventAt = Date.now();
  let watchdog: number | null = null;

  const emit = (evt: MonitoringEvent) => {
    lastEventAt = Date.now();
    if (evt.type === 'service') snapshot.serviceStatus = evt.serviceStatus;
    if (evt.type === 'run' && evt.run.runId) {
      snapshot.run = { ...(snapshot.run ?? (evt.run as RunSnapshot)), ...evt.run } as RunSnapshot;
      if (evt.run.serviceStatus) snapshot.serviceStatus = evt.run.serviceStatus;
    }
    if (evt.type === 'resources') snapshot.resources = evt.resources;
    if (evt.type === 'adapterError') snapshot.serviceStatus = 'disconnected';
    for (const listener of listeners) listener(evt);
  };

  const stopPoll = () => {
    if (pollTimer !== null) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  };

  const startPoll = () => {
    if (pollTimer !== null) return;
    const pull = async () => {
      try {
        const run = await apiFetch<RunSnapshot | null>('/run');
        if (run) {
          emit({ type: 'run', run });
          if (run.serviceStatus) {
            emit({ type: 'service', serviceStatus: run.serviceStatus, errorMessage: run.errorMessage });
          }
        } else {
          emit({ type: 'service', serviceStatus: 'stopped' });
        }
      } catch {
        emit({ type: 'service', serviceStatus: 'disconnected' });
        emit({ type: 'adapterError', messageKey: 'monitoring.empty.disconnectedTitle' });
      }
    };
    void pull();
    pollTimer = window.setInterval(() => void pull(), 1500);
  };

  const closeSource = () => {
    source?.close();
    source = null;
  };

  const connect = () => {
    closeSource();
    try {
      const es = new EventSource(`${API_BASE}/run/stream`);
      source = es;
      const names = ['service', 'run', 'resources', 'log', 'chat'] as const;
      for (const name of names) {
        es.addEventListener(name, (event) => {
          retry = 1000;
          const parsed = parseEvent(name, (event as MessageEvent<string>).data);
          if (parsed) emit(parsed);
        });
      }
      es.onopen = () => {
        retry = 1000;
        lastEventAt = Date.now();
      };
      es.onerror = () => {
        closeSource();
        emit({ type: 'service', serviceStatus: 'disconnected' });
        if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
        reconnectTimer = window.setTimeout(() => {
          retry = Math.min(retry * 2, 15_000);
          if (retry >= 8_000) {
            startPoll();
            return;
          }
          connect();
        }, retry);
      };
    } catch {
      startPoll();
    }
  };

  const startWatchdog = () => {
    if (watchdog !== null) return;
    watchdog = window.setInterval(() => {
      if (Date.now() - lastEventAt > 20_000 && snapshot.serviceStatus !== 'stopped') {
        emit({ type: 'service', serviceStatus: 'disconnected' });
      }
    }, 5000);
  };

  return {
    subscribe(cb) {
      listeners.add(cb);
      if (listeners.size === 1) {
        connect();
        startWatchdog();
      }
      return () => {
        listeners.delete(cb);
        if (listeners.size === 0) {
          closeSource();
          stopPoll();
          if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
          if (watchdog !== null) window.clearInterval(watchdog);
          reconnectTimer = null;
          watchdog = null;
        }
      };
    },
    getSnapshot() {
      return { ...snapshot };
    },
    sendChat(text: string) {
      void apiFetch('/run/chat', { method: 'POST', body: JSON.stringify({ text }) }).catch(() => {
        emit({ type: 'adapterError', messageKey: 'monitoring.empty.errorTitle' });
      });
    },
    abortChat() {
      void apiFetch('/run/chat/abort', { method: 'POST' }).catch(() => undefined);
    },
  };
}
