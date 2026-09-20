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
          {!isUser && message.sources ? <Sources sources={message.sources} /> : null}
        </div>
        <time className="text-[11px] text-muted-foreground">{time}</time>
      </div>
    </article>
  );
}

export function HelpChatMessages({
  messages,
  streaming,
}: {
  messages: HelpMessage[];
  streaming?: HelpMessage | null;
}) {
  const { t, i18n } = useTranslation();
  const endRef = useRef<HTMLDivElement>(null);
  const items = streaming ? [...messages, streaming] : messages;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [items.length, streaming?.content]);

  if (items.length === 0) {
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
        <div ref={endRef} />
      </div>
    </ScrollArea>
  );
}
