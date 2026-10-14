import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { MessageCircleQuestion, Square, Send } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { abortRunChat, sendRunChat } from '@/modules/monitoring/live/adapter';
import { chatInputConfig } from '@/modules/monitoring/model/graph';
import { formatTime } from '@/modules/monitoring/model/format';
import { formatChatBody } from '@/modules/monitoring/model/logMessage';
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
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const stickToBottom = useRef(true);
  const pendingFocus = useMonitoringStore((state) => state.pendingChatFocus);
  const setPendingChatFocus = useMonitoringStore((state) => state.setPendingChatFocus);
  const config = chatInputConfig(run.graph);
  const running = serviceStatus === 'running';
  const waitingHuman =
    running && Object.values(run.nodesRuntime).some((node) => node.waitReason === 'human');
  const waitingInput = waitingHuman && messages.length === 0;
  const lastContent = messages[messages.length - 1]?.content;

  useEffect(() => {
    const el = listRef.current;
    if (!el || !stickToBottom.current) return;
    el.scrollTop = el.scrollHeight;
  }, [generating, lastContent, messages.length]);

  useEffect(() => {
    if (!pendingFocus) return;
    inputRef.current?.focus({ preventScroll: true });
    setPendingChatFocus(false);
  }, [pendingFocus, setPendingChatFocus]);

  const waitingReply = waitingHuman && messages.length > 0;

  function onListScroll() {
    const el = listRef.current;
    if (!el) return;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 64;
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const value = text.trim();
    if (!value || !running || generating) return;
    stickToBottom.current = true;
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
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div
        ref={listRef}
        onScroll={onListScroll}
        className="min-h-0 flex-1 space-y-3 overflow-auto px-1 py-2 [overflow-anchor:none]"
      >
        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {waitingInput ? t('monitoring.chat.waitInput') : t('monitoring.chat.empty')}
          </p>
        ) : (
          messages.map((message) => <Bubble key={message.id} message={message} locale={i18n.language} />)
        )}
      </div>
      {waitingReply ? (
        <Alert className="mb-2 border-warning/50 bg-warning/10 [&>svg]:text-warning [&>div]:pl-6">
          <MessageCircleQuestion className="size-4" />
          <AlertTitle>{t('shell.waitAsk')}</AlertTitle>
          <AlertDescription>{t('monitoring.chat.waitReply')}</AlertDescription>
        </Alert>
      ) : null}
      <form
        onSubmit={submit}
        className={cn('flex items-end gap-2 border-t pt-3', waitingReply && 'rounded-md border-warning/60')}
      >
        <Textarea
          ref={inputRef}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          disabled={!running}
          placeholder={config?.placeholder || t('monitoring.chat.placeholder')}
          className={cn(
            'min-h-[44px] max-h-32 flex-1',
            waitingReply && 'border-warning focus-visible:border-warning',
          )}
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
  const { t } = useTranslation();
  const user = message.role === 'user';
  return (
    <article className={cn('flex flex-col gap-1', user ? 'items-end' : 'items-start')}>
      <div
        className={cn(
          'max-w-[92%] whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm',
          user ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground',
        )}
      >
        {formatChatBody(message, t)}
      </div>
      <time className="text-[11px] text-muted-foreground">{formatTime(message.createdAt, locale)}</time>
    </article>
  );
}
