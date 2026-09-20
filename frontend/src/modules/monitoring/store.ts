import { create } from 'zustand';
import { notify } from '@/lib/notifications';
import { useAppStore } from '@/store';
import type { ServiceStatus } from '@/store/session';
import { loadLatestHistoryRun } from '@/modules/monitoring/model/archive';
import {
  applyChatDelta,
  hasChatInput,
  mergeRunSnapshot,
  upsertChat,
} from '@/modules/monitoring/model/graph';
import { maskLog, maskText } from '@/modules/monitoring/model/mask';
import type {
  ChatMessage,
  LogEvent,
  LogLevel,
  MonitoringEvent,
  ResourceSnapshot,
  RunSnapshot,
} from '@/modules/monitoring/model/types';
import { LOG_BUFFER_SIZE } from '@/modules/monitoring/model/types';

type MonitoringTab = 'chat' | 'log';

type MonitoringState = {
  run: RunSnapshot | null;
  resources: ResourceSnapshot | null;
  logs: LogEvent[];
  chatMessages: ChatMessage[];
  chatGenerating: boolean;
  adapterErrorKey: string | null;
  lastErrorMessage: string | null;
  tab: MonitoringTab;
  logLevelMin: LogLevel;
  logQuery: string;
  logNodeId: string | null;
  logErrorsOnly: boolean;
  autoscroll: boolean;
  unseenCount: number;
  selectedLogId: string | null;
  selectedNodeId: string | null;
  lastNotifyKey: string;
  setTab: (tab: MonitoringTab) => void;
  setLogLevelMin: (level: LogLevel) => void;
  setLogQuery: (query: string) => void;
  setLogNodeId: (id: string | null) => void;
  setLogErrorsOnly: (value: boolean) => void;
  setAutoscroll: (value: boolean) => void;
  setSelectedLogId: (id: string | null) => void;
  setSelectedNodeId: (id: string | null) => void;
  setChatGenerating: (value: boolean) => void;
  clearLogFilter: () => void;
};

let lastService: ServiceStatus | null = null;
let lastStepKey = '';

function toastOnce(key: string, titleKey: string, variant: 'success' | 'info' | 'error', descriptionKey?: string) {
  const state = useMonitoringStore.getState();
  if (state.lastNotifyKey === key) return;
  useMonitoringStore.setState({ lastNotifyKey: key });
  notify({ titleKey, descriptionKey, variant });
}

function notifyTransitions(next: ServiceStatus, runId: string | undefined, errorMessage?: string) {
  const prev = lastService;
  lastService = next;
  if (!prev || prev === next) return;
  if (next === 'running' && (prev === 'stopped' || prev === 'starting' || prev === 'disconnected')) {
    toastOnce(`start:${runId ?? 'x'}`, 'monitoring.notify.runStarted', 'success');
  }
  if (next === 'stopped' && (prev === 'running' || prev === 'stopping')) {
    toastOnce(`stop:${runId ?? 'x'}`, 'monitoring.notify.runStopped', 'info');
  }
  if (
    (next === 'disconnected' || next === 'error') &&
    (prev === 'running' || prev === 'starting')
  ) {
    toastOnce(`disc:${next}`, 'monitoring.notify.disconnected', 'error', errorMessage ? undefined : 'monitoring.empty.disconnectedBody');
  }
}

export const useMonitoringStore = create<MonitoringState>((set) => ({
  run: null,
  resources: null,
  logs: [],
  chatMessages: [],
  chatGenerating: false,
  adapterErrorKey: null,
  lastErrorMessage: null,
  tab: 'log',
  logLevelMin: 'info',
  logQuery: '',
  logNodeId: null,
  logErrorsOnly: false,
  autoscroll: true,
  unseenCount: 0,
  selectedLogId: null,
  selectedNodeId: null,
  lastNotifyKey: '',
  setTab: (tab) => set({ tab }),
  setLogLevelMin: (logLevelMin) => set({ logLevelMin }),
  setLogQuery: (logQuery) => set({ logQuery }),
  setLogNodeId: (logNodeId) => set({ logNodeId }),
  setLogErrorsOnly: (logErrorsOnly) => set({ logErrorsOnly }),
  setAutoscroll: (autoscroll) =>
    set({ autoscroll, unseenCount: autoscroll ? 0 : useMonitoringStore.getState().unseenCount }),
  setSelectedLogId: (selectedLogId) => set({ selectedLogId }),
  setSelectedNodeId: (selectedNodeId) => set({ selectedNodeId }),
  setChatGenerating: (chatGenerating) => set({ chatGenerating }),
  clearLogFilter: () => set({ logNodeId: null }),
}));

function tabForRun(run: RunSnapshot | null, preferred: MonitoringTab): MonitoringTab {
  if (preferred === 'chat' && hasChatInput(run?.graph)) return 'chat';
  return 'log';
}

function resetForRun(run: RunSnapshot | null): Partial<MonitoringState> {
  return {
    logs: [],
    chatMessages: run?.chat?.messages ?? [],
    chatGenerating: Boolean(run?.chat?.generating),
    tab: tabForRun(run, useMonitoringStore.getState().tab),
    logQuery: '',
    logNodeId: null,
    logErrorsOnly: false,
    autoscroll: true,
    unseenCount: 0,
    selectedLogId: null,
    selectedNodeId: null,
  };
}

export async function hydrateLastRun() {
  const busy = () => {
    const status = useAppStore.getState().serviceStatus;
    return status === 'running' || status === 'starting';
  };
  if (busy()) return;
  try {
    const loaded = await loadLatestHistoryRun();
    if (!loaded || busy()) return;
    const now = useMonitoringStore.getState();
    if (now.run && !now.run.archived) return;
    if (now.run?.archived && now.run.runId === loaded.run.runId && now.logs.length > 0) return;
    useMonitoringStore.setState({
      run: loaded.run,
      logs: loaded.logs,
      lastErrorMessage: loaded.run.errorMessage ?? now.lastErrorMessage,
      ...resetForRun(loaded.run),
      chatMessages: loaded.run.chat?.messages ?? [],
      chatGenerating: false,
    });
  } catch {
    /* keep current snapshot */
  }
}

export function hydrateMonitoring(snapshot: {
  serviceStatus: ServiceStatus;
  run: RunSnapshot | null;
  resources: ResourceSnapshot | null;
}) {
  const store = useAppStore.getState();
  store.setServiceStatus(snapshot.serviceStatus);
  store.setRunId(snapshot.run?.runId ?? store.runId);
  lastService = snapshot.serviceStatus;
  useMonitoringStore.setState({
    run: snapshot.run,
    resources: snapshot.resources,
    logs: [],
    chatMessages: snapshot.run?.chat?.messages ?? [],
    chatGenerating: Boolean(snapshot.run?.chat?.generating),
    adapterErrorKey: null,
    lastErrorMessage: snapshot.run?.errorMessage ?? null,
    tab: tabForRun(snapshot.run, useMonitoringStore.getState().tab),
  });
}

export function applyMonitoringEvent(evt: MonitoringEvent) {
  const current = useMonitoringStore.getState();
  const app = useAppStore.getState();

  if (evt.type === 'adapterError') {
    useMonitoringStore.setState({ adapterErrorKey: evt.messageKey });
    return;
  }

  if (evt.type === 'service') {
    app.setServiceStatus(evt.serviceStatus);
    if (evt.serviceStatus === 'stopped') app.setRunId(null);
    notifyTransitions(evt.serviceStatus, current.run?.runId, evt.errorMessage);
    useMonitoringStore.setState({
      lastErrorMessage: evt.errorMessage ?? (evt.serviceStatus === 'error' ? current.lastErrorMessage : null),
      adapterErrorKey: evt.serviceStatus === 'disconnected' ? 'monitoring.empty.disconnectedTitle' : null,
      run:
        current.run && evt.serviceStatus === 'stopped'
          ? { ...current.run, archived: true, serviceStatus: 'stopped' }
          : current.run
            ? { ...current.run, serviceStatus: evt.serviceStatus, errorMessage: evt.errorMessage }
            : current.run,
      resources: evt.serviceStatus === 'stopped' ? null : current.resources,
    });
    if (evt.serviceStatus === 'stopped') void hydrateLastRun();
    return;
  }

  if (evt.type === 'resources') {
    useMonitoringStore.setState({ resources: evt.resources });
    return;
  }

  if (evt.type === 'log') {
    if (current.run?.archived && evt.log.runId && evt.log.runId !== current.run.runId) return;
    if (current.logs.some((item) => item.id === evt.log.id)) return;
    const masked = maskLog(evt.log);
    const log: LogEvent = { ...evt.log, ...masked };
    const logs = [...current.logs, log];
    if (logs.length > LOG_BUFFER_SIZE) logs.splice(0, logs.length - LOG_BUFFER_SIZE);
    useMonitoringStore.setState({
      logs,
      unseenCount: current.autoscroll ? 0 : current.unseenCount + 1,
    });
    return;
  }

  if (evt.type === 'chat') {
    if (current.run?.archived && evt.runId && evt.runId !== current.run.runId) return;
    let messages = current.chatMessages;
    let generating = current.chatGenerating;
    if (evt.message) {
      const message: ChatMessage = {
        ...evt.message,
        content: maskText(evt.message.content),
      };
      messages = upsertChat(messages, message);
      generating = message.role === 'user' ? true : false;
    }
    if (evt.delta && evt.id) {
      messages = applyChatDelta(messages, evt.runId, evt.id, maskText(evt.delta));
      generating = true;
    }
    useMonitoringStore.setState({ chatMessages: messages, chatGenerating: generating });
    return;
  }

  if (evt.type === 'run') {
    const prevId = current.run?.runId;
    const status = evt.run.serviceStatus ?? app.serviceStatus;
    const fromArchive =
      Boolean(current.run?.archived && evt.run.runId && evt.run.runId !== current.run.runId);
    const merged = mergeRunSnapshot(fromArchive ? null : current.run, {
      ...evt.run,
      archived: status === 'stopped',
    });
    if (!merged) return;
    const isNew = Boolean(merged.runId && merged.runId !== prevId);
    app.setRunId(merged.runId);
    if (merged.serviceStatus) {
      app.setServiceStatus(merged.serviceStatus);
      notifyTransitions(merged.serviceStatus, merged.runId, merged.errorMessage);
    }
    const step = merged.activity.stepError;
    const stepKey = step ? `${merged.runId}:${step.nodeId}:${step.message}` : '';
    if (step && stepKey !== lastStepKey) {
      lastStepKey = stepKey;
      toastOnce(stepKey, 'monitoring.notify.stepFailed', 'error');
    }
    if (!step) lastStepKey = '';
    const incoming = merged.chat?.messages ?? [];
    let chatMessages = current.chatMessages;
    let chatGenerating = current.chatGenerating;
    if (isNew) {
      chatMessages = incoming;
      chatGenerating = Boolean(merged.chat?.generating);
    } else if (incoming.length > 0) {
      let next = chatMessages;
      for (const message of incoming) {
        next = upsertChat(next, { ...message, content: maskText(message.content) });
      }
      chatMessages = next;
      if (typeof merged.chat?.generating === 'boolean') {
        chatGenerating = merged.chat.generating;
      }
    }
    useMonitoringStore.setState({
      run: merged,
      lastErrorMessage: merged.errorMessage ?? current.lastErrorMessage,
      ...(isNew ? resetForRun(merged) : null),
      chatMessages,
      chatGenerating,
    });
  }
}
