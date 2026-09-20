import { useQuery } from '@tanstack/react-query';
import { API_BASE, apiFetch, queryClient } from '@/api/client';
import type { HelpChatStatus, HelpMessage, HelpSendHandlers, HelpSource } from '@/components/help-chat/model';
import i18n, { resolveAppLanguage } from '@/i18n';

export async function getHelpChatStatus(): Promise<HelpChatStatus> {
  return apiFetch<HelpChatStatus>('/help-chat/status');
}

export async function setOnboardingSeen(): Promise<void> {
  await apiFetch('/settings', {
    method: 'PATCH',
    body: JSON.stringify({ chatOnboardingSeen: true }),
  });
  queryClient.setQueryData(['help-chat', 'status'], (current: HelpChatStatus | undefined) =>
    current ? { ...current, onboardingSeen: true } : current,
  );
  await queryClient.invalidateQueries({ queryKey: ['help-chat', 'status'] });
  await queryClient.invalidateQueries({ queryKey: ['settings'] });
}

export async function listHelpMessages(): Promise<HelpMessage[]> {
  const body = await apiFetch<{ items: HelpMessage[] }>('/help-chat/messages');
  return body.items;
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
  const controller = new AbortController();
  void (async () => {
    try {
      const response = await fetch(`${API_BASE}/help-chat/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ text, locale: resolveAppLanguage(i18n.language) }),
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
