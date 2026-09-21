import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { BrandMark } from '@/components/BrandMark';
import { LightMarkdown } from '@/components/help-chat/markdown';
import type { HelpMessage, HelpSource } from '@/components/help-chat/model';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';

function Sources({ sources }: { sources: HelpSource[] }) {
  const { t } = useTranslation();
  if (sources.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1 border-t border-border/60 pt-2 text-xs text-muted-foreground">
      {sources.map((source, index) => (
        <li key={`${source.kind}-${source.title}-${index}`}>
          {source.kind === 'web' && source.url ? (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2"
            >
              {t('helpChat.sources.web')}: {source.title}
            </a>
          ) : (
            <span>
              {t('helpChat.sources.rag')}: {source.title}
              {source.section ? ` — ${source.section}` : ''}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function TypingIndicator() {
  const { t } = useTranslation();
  return (
    <div className="flex gap-2" role="status" aria-live="polite" aria-label={t('helpChat.status.generating')}>
      <span className="relative mt-0.5 size-7 shrink-0">
        <span
          aria-hidden
          className="absolute -inset-1 rounded-full border border-warning/80 motion-safe:animate-help-typing-ring"
        />
        <BrandMark className="relative size-7" alt="" />
      </span>
      <div className="relative flex h-9 items-center gap-1.5 overflow-hidden rounded-lg bg-muted px-3.5">
        <span
          aria-hidden
          className="pointer-events-none absolute inset-y-1 left-0 w-5 rounded-full bg-warning/45 blur-md motion-safe:animate-help-typing-sweep"
        />
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            aria-hidden
            className="relative size-1.5 rounded-full bg-muted-foreground/40 motion-safe:animate-help-typing-dot"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

function Bubble({
  message,
  locale,
}: {
  message: HelpMessage;
  locale: string;
}) {
  const time = new Date(message.createdAt).toLocaleTimeString(locale, {
    hour: '2-digit',
    minute: '2-digit',
  });
  const isUser = message.role === 'user';
  return (
    <article className={cn('flex gap-2', isUser ? 'flex-row-reverse' : 'flex-row')}>
      {!isUser ? <BrandMark className="mt-0.5 size-7" alt="" /> : <span className="size-7 shrink-0" />}
      <div className={cn('flex min-w-0 flex-col gap-1', isUser ? 'items-end' : 'items-start')}>
        <div
          className={cn(
            'max-w-full rounded-lg px-3 py-2',
            isUser ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground',
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words text-sm leading-6">{message.content}</p>
          ) : (
            <LightMarkdown text={message.content} />
          )}
          {!isUser && message.sources ? (
            <Sources sources={message.sources.filter((source) => source.kind === 'web')} />
          ) : null}
        </div>
        <time className="text-[11px] text-muted-foreground">{time}</time>
      </div>
    </article>
  );
}

export function HelpChatMessages({
  messages,
  streaming,
  waiting = false,
}: {
  messages: HelpMessage[];
  streaming?: HelpMessage | null;
  waiting?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const endRef = useRef<HTMLDivElement>(null);
  const items = streaming ? [...messages, streaming] : messages;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [items.length, streaming?.content, waiting]);

  if (items.length === 0 && !waiting) {
    return (
      <div className="flex flex-1 items-center justify-center p-4 text-center text-sm text-muted-foreground">
        {t('helpChat.empty')}
      </div>
    );
  }

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="flex flex-col gap-3 p-3">
        {items.map((message) => (
          <Bubble key={message.id} message={message} locale={i18n.language} />
        ))}
        {waiting ? <TypingIndicator /> : null}
        <div ref={endRef} />
      </div>
    </ScrollArea>
  );
}
