import { useEffect, useRef } from 'react';
import { useCopySelection } from '@/lib/copySelection';
import { useTranslation } from 'react-i18next';
import { BrandMark } from '@/components/BrandMark';
import { MarkdownView } from '@/components/MarkdownView';
import type { HelpMessage, HelpSource } from '@/components/help-chat/model';
import { ScrollArea } from '@/components/ui/scroll-area';
import { getChromeHost } from '@/lib/chromeHost';
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
              onClick={(event) => {
                const openExternal = getChromeHost()?.openExternal;
                if (!openExternal) return;
                event.preventDefault();
                void openExternal(source.url!);
              }}
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
    <div className="flex items-end gap-2" role="status" aria-live="polite" aria-label={t('helpChat.status.generating')}>
      <BrandMark spinning className="size-12" alt="" />
      <div className="relative mb-1.5 flex h-7 items-center gap-1 overflow-hidden rounded-lg bg-muted px-2.5">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            aria-hidden
            className="relative size-1 rounded-full bg-muted-foreground/40 motion-safe:animate-help-typing-dot"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

/** Time of day; the date too when the message is not from today. */
function stamp(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const today = new Date().toDateString() === date.toDateString();
  return date.toLocaleString(
    locale,
    today ? { hour: '2-digit', minute: '2-digit' } : { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' },
  );
}

function Bubble({
  message,
  locale,
  spinning = false,
  chill = false,
}: {
  message: HelpMessage;
  locale: string;
  spinning?: boolean;
  chill?: boolean;
}) {
  const time = stamp(message.createdAt, locale);
  const isUser = message.role === 'user';
  return (
    <article className={cn('flex gap-2', isUser ? 'justify-end' : 'flex-row')}>
      {!isUser ? <BrandMark spinning={spinning} chill={chill} className="mt-0.5 size-12" alt="" /> : null}
      <div className={cn('flex min-w-0 flex-col gap-1', isUser ? 'items-end' : 'items-start')}>
        <div
          className={cn(
            'max-w-full cursor-text select-text rounded-lg px-3 py-2',
            isUser ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground',
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words text-sm leading-6">{message.content}</p>
          ) : (
            <MarkdownView text={message.content} bare small />
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
  const listRef = useRef<HTMLDivElement>(null);
  useCopySelection(listRef);
  const items = streaming ? [...messages, streaming] : messages;
  const lastAssistantId = [...items].reverse().find((message) => message.role === 'assistant')?.id;
  const chillLast = Boolean(lastAssistantId) && !waiting && !streaming;

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
    // Radix lays the viewport content out as a table, which grows with the longest word
    // instead of wrapping; as a block it follows the panel width when it is resized.
    <ScrollArea className="min-h-0 flex-1 [&_[data-radix-scroll-area-viewport]>div]:!block">
      <div ref={listRef} className="flex flex-col gap-3 p-3">
        {items.map((message) => (
          <Bubble
            key={message.id}
            message={message}
            locale={i18n.language}
            spinning={message.id === 'streaming'}
            chill={chillLast && message.id === lastAssistantId}
          />
        ))}
        {waiting ? <TypingIndicator /> : null}
        <div ref={endRef} />
      </div>
    </ScrollArea>
  );
}
