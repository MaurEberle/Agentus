import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Square, Send } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { abortRunChat, sendRunChat } from '@/modules/monitoring/live/adapter';
import { chatInputConfig } from '@/modules/monitoring/model/graph';
import { formatTime } from '@/modules/monitoring/model/format';
import type { ChatMessage, RunSnapshot } from '@/modules/monitoring/model/types';
import { useMonitoringStore } from '@/modules/monitoring/store';
import type { ServiceStatus } from '@/store/session';

export function NetworkChat({
  run,
  serviceStatus,
}: {
  run: RunSnapshot;
  serviceStatus: ServiceStatus;
}) {
  const { t, i18n } = useTranslation();
  const messages = useMonitoringStore((state) => state.chatMessages);
  const generating = useMonitoringStore((state) => state.chatGenerating);
  const [text, setText] = useState('');
  const endRef = useRef<HTMLDivElement>(null);
  const config = chatInputConfig(run.graph);
  const running = serviceStatus === 'running';
  const waitingInput =
    running &&
    messages.length === 0 &&
    (Boolean(config?.requireInput) ||
      Object.values(run.nodesRuntime).some((node) => node.waitReason === 'human'));

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [messages, generating]);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const value = text.trim();
    if (!value || !running || generating) return;
    sendRunChat(value);
    setText('');
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex min-h-[240px] flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-auto px-1 py-2">
        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {waitingInput ? t('monitoring.chat.waitInput') : t('monitoring.chat.empty')}
          </p>
        ) : (
          messages.map((message) => <Bubble key={message.id} message={message} locale={i18n.language} />)
        )}
        <div ref={endRef} />
      </div>
      <form onSubmit={submit} className="flex items-end gap-2 border-t pt-3">
        <Textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          disabled={!running}
          placeholder={config?.placeholder || t('monitoring.chat.placeholder')}
          className="min-h-[44px] max-h-32 flex-1"
          rows={2}
        />
        {generating ? (
          <Button type="button" variant="outline" onClick={() => abortRunChat()}>
            <Square className="size-4" />
            <span className="sr-only sm:not-sr-only sm:ml-2">{t('monitoring.chat.stop')}</span>
          </Button>
        ) : (
          <Button type="submit" disabled={!running || !text.trim()}>
            <Send className="size-4" />
            <span className="sr-only sm:not-sr-only sm:ml-2">{t('monitoring.chat.send')}</span>
          </Button>
        )}
      </form>
      {!running ? <p className="pt-2 text-xs text-muted-foreground">{t('monitoring.chat.disabled')}</p> : null}
    </div>
  );
}

function Bubble({ message, locale }: { message: ChatMessage; locale: string }) {
  const user = message.role === 'user';
  return (
    <article className={cn('flex flex-col gap-1', user ? 'items-end' : 'items-start')}>
      <div
        className={cn(
          'max-w-[92%] whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm',
          user ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground',
        )}
      >
        {message.content}
      </div>
      <time className="text-[11px] text-muted-foreground">{formatTime(message.createdAt, locale)}</time>
    </article>
  );
}
