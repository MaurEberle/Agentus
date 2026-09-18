import { useQuery } from '@tanstack/react-query';
import { API_BASE, USE_MOCKS, apiFetch, queryClient } from '@/api/client';
import i18n from '@/i18n';
import { helpMessageCache } from '@/components/help-chat/messageStore';
import { mockGetSettings, mockPatchSettings } from '@/modules/settings/mocks';
import { helpChatConfigured } from '@/modules/settings/model';
import type { HelpChatStatus, HelpMessage, HelpSendHandlers, HelpSource } from '@/components/help-chat/model';
import { useAppStore } from '@/store';

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function getHelpChatStatus(): Promise<HelpChatStatus> {
  if (!USE_MOCKS) return apiFetch<HelpChatStatus>('/help-chat/status');
  const settings = await mockGetSettings();
  const serviceStatus = useAppStore.getState().serviceStatus;
  return {
    configured: helpChatConfigured(settings.helpChat),
    onboardingSeen: Boolean(settings.chatOnboardingSeen),
    webSearchEnabled: settings.helpChat.webSearchEnabled,
    degraded: serviceStatus === 'running' || serviceStatus === 'starting',
  };
}

export async function setOnboardingSeen(): Promise<void> {
  if (USE_MOCKS) await mockPatchSettings({ chatOnboardingSeen: true });
  else {
    await apiFetch('/settings', {
      method: 'PATCH',
      body: JSON.stringify({ chatOnboardingSeen: true }),
    });
  }
  queryClient.setQueryData(['help-chat', 'status'], (current: HelpChatStatus | undefined) =>
    current ? { ...current, onboardingSeen: true } : current,
  );
  await queryClient.invalidateQueries({ queryKey: ['help-chat', 'status'] });
  await queryClient.invalidateQueries({ queryKey: ['settings'] });
}

export async function listHelpMessages(): Promise<HelpMessage[]> {
  if (USE_MOCKS) {
    await delay(20);
    return helpMessageCache.map((item) => ({
      ...item,
      sources: item.sources ? [...item.sources] : undefined,
    }));
  }
  const body = await apiFetch<{ items: HelpMessage[] }>('/help-chat/messages');
  return body.items;
}

function mockSend(text: string, handlers: HelpSendHandlers): { abort: () => void } {
  let aborted = false;
  helpMessageCache.push({
    id: crypto.randomUUID(),
    role: 'user',
    content: text,
    createdAt: new Date().toISOString(),
  });
  queryClient.setQueryData(['help-chat', 'messages'], [...helpMessageCache]);

  const reply = i18n.t('helpChat.mock.reply');
  const chunks = reply.split(/(\s+)/).filter((part) => part.length > 0);
  let index = 0;
  let content = '';
  const id = crypto.randomUUID();
  const createdAt = new Date().toISOString();

  const finish = (sources?: HelpSource[]) => {
    const final: HelpMessage = { id, role: 'assistant', content, createdAt, sources };
    helpMessageCache.push(final);
    handlers.onDone(final);
    void queryClient.invalidateQueries({ queryKey: ['help-chat', 'messages'] });
  };

  const timer = setInterval(() => {
    if (aborted) return;
    if (index < chunks.length) {
      const chunk = chunks[index] ?? '';
      index += 1;
      content += chunk;
      handlers.onDelta(chunk);
      return;
    }
    clearInterval(timer);
    void getHelpChatStatus().then((status) => {
      if (aborted) return;
      const sources: HelpSource[] = [
        {
          kind: 'rag',
          title: i18n.t('helpChat.mock.ragTitle'),
          section: i18n.t('helpChat.mock.ragSection'),
        },
      ];
      if (status.webSearchEnabled) {
        sources.push({
          kind: 'web',
          title: i18n.t('helpChat.mock.webTitle'),
          url: 'https://docs.ollama.com',
        });
      }
      handlers.onSources?.(sources);
      finish(sources);
    });
  }, 40);

  return {
    abort: () => {
      aborted = true;
      clearInterval(timer);
      if (content) finish();
    },
  };
}

async function readSse(response: Response, handlers: HelpSendHandlers) {
  if (!response.body) {
    handlers.onError({ messageKey: 'helpChat.error.generic' });
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let eventName = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        const payload = JSON.parse(line.slice(5).trim()) as {
          chunk?: string;
          sources?: HelpSource[];
          message?: HelpMessage;
          messageKey?: string;
        };
        if (eventName === 'delta' && payload.chunk) handlers.onDelta(payload.chunk);
        if (eventName === 'sources' && payload.sources) handlers.onSources?.(payload.sources);
        if (eventName === 'done' && payload.message) handlers.onDone(payload.message);
        if (eventName === 'error') handlers.onError({ messageKey: payload.messageKey });
      } else if (line.trim() === '') {
        eventName = '';
      }
    }
  }
}

export function sendHelpMessage(text: string, handlers: HelpSendHandlers): { abort: () => void } {
  if (USE_MOCKS) return mockSend(text, handlers);

  const controller = new AbortController();
  void (async () => {
    try {
      const response = await fetch(`${API_BASE}/help-chat/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });
      if (!response.ok) {
        handlers.onError({ messageKey: 'helpChat.error.generic' });
        return;
      }
      await readSse(response, handlers);
      await queryClient.invalidateQueries({ queryKey: ['help-chat', 'messages'] });
    } catch {
      if (controller.signal.aborted) {
        void apiFetch('/help-chat/abort', { method: 'POST' });
        return;
      }
      handlers.onError({ messageKey: 'helpChat.error.generic' });
    }
  })();

  return {
    abort: () => {
      controller.abort();
      void apiFetch('/help-chat/abort', { method: 'POST' });
    },
  };
}

export function useHelpChatStatusQuery() {
  return useQuery({
    queryKey: ['help-chat', 'status'],
    queryFn: getHelpChatStatus,
    refetchInterval: 4000,
  });
}



export function useHelpMessagesQuery() {
  return useQuery({
    queryKey: ['help-chat', 'messages'],
    queryFn: listHelpMessages,
  });
}
