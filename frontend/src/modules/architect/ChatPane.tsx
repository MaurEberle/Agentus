import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ChevronRight, CircleAlert, LoaderCircle, Send, Square, Wrench } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { BrandMark } from '@/components/BrandMark';
import { MarkdownView } from '@/components/MarkdownView';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import type { ArchitectMessage, ToolLine } from '@/modules/architect/api';

export type LiveTool = { id: string; name: string; status: 'running' | 'done' | 'failed'; key?: string; params?: Record<string, unknown> };

function Tools({ tools }: { tools: ToolLine[] }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  if (tools.length === 0) return null;
  return (
    <div className="text-xs text-muted-foreground">
      <button type="button" className="flex items-center gap-1 hover:text-foreground" onClick={() => setOpen((value) => !value)}>
        <ChevronRight className={cn('size-3.5 transition-transform', open && 'rotate-90')} aria-hidden />
        <Wrench className="size-3.5" aria-hidden />
        {t('architect.chat.tools', { count: tools.length })}
      </button>
      {open ? (
        <ul className="mt-1 grid gap-0.5 ps-5">
          {tools.map((tool, index) => (
            <li key={index} className={tool.ok ? undefined : 'text-destructive'}>
              {t(tool.key, { ...tool.params, defaultValue: tool.name })}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function Bubble({ message }: { message: ArchitectMessage }) {
  const user = message.role === 'user';
  return (
    <article className={cn('flex gap-2', user ? 'justify-end' : 'flex-row')}>
      {!user ? <BrandMark className="mt-0.5 size-10 shrink-0" alt="" /> : null}
      <div className={cn('flex min-w-0 max-w-[85%] flex-col gap-1', user ? 'items-end' : 'items-start')}>
        {message.content ? (
          <div className={cn('max-w-full rounded-lg px-3 py-2', user ? 'bg-primary text-primary-foreground' : 'bg-muted')}>
            {user ? (
              <p className="whitespace-pre-wrap break-words text-sm leading-6">{message.content}</p>
            ) : (
              <MarkdownView text={message.content} bare small />
            )}
          </div>
        ) : null}
        {!user ? <Tools tools={message.tools} /> : null}
      </div>
    </article>
  );
}

const EXAMPLES = ['architect.examples.coding', 'architect.examples.research', 'architect.examples.documents'] as const;

/** The conversation with the architect, live tool lines, the idle notice and the input. */
export function ChatPane({
  messages,
  streaming,
  liveTools,
  pendingUser,
  sending,
  active,
  idleLeft,
  error,
  banner,
  onSend,
  onAbort,
  onKeepAlive,
}: {
  messages: ArchitectMessage[];
  streaming: string;
  liveTools: LiveTool[];
  pendingUser: string | null;
  sending: boolean;
  active: boolean;
  idleLeft: number | null;
  error: string | null;
  /** Shown above the input: what the architect waits on (ProposalCard). */
  banner?: ReactNode;
  onSend: (text: string) => void;
  onAbort: () => void;
  onKeepAlive: () => void;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState('');
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [messages.length, streaming, liveTools.length, pendingUser]);

  function send(text: string) {
    const value = text.trim();
    if (!value || !active || sending) return;
    setDraft('');
    onSend(value);
  }

  const empty = messages.length === 0 && !pendingUser;
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-auto">
        <div className="flex flex-col gap-3 p-3">
          {empty ? (
            <div className="grid gap-3 py-6 text-center">
              <p className="text-sm text-muted-foreground">{t(active ? 'architect.chat.emptyActive' : 'architect.chat.emptyIdle')}</p>
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLES.map((key) => (
                  <button
                    key={key}
                    type="button"
                    disabled={!active}
                    onClick={() => send(t(key))}
                    className="rounded-full border px-3 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
                  >
                    {t(key)}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {messages.map((message) => (
            <Bubble key={message.id} message={message} />
          ))}
          {pendingUser ? (
            <Bubble message={{ id: 'pending', role: 'user', content: pendingUser, createdAt: '', tools: [] }} />
          ) : null}
          {sending ? (
            <article className="flex gap-2">
              <BrandMark spinning className="mt-0.5 size-10 shrink-0" alt="" />
              <div className="flex min-w-0 max-w-[85%] flex-col gap-1">
                {liveTools.map((tool) => (
                  <p key={tool.id} className={cn('flex items-center gap-1.5 text-xs', tool.status === 'failed' ? 'text-destructive' : 'text-muted-foreground')}>
                    {tool.status === 'running' ? <LoaderCircle className="size-3.5 animate-spin" aria-hidden /> : <Wrench className="size-3.5" aria-hidden />}
                    {tool.key ? t(tool.key, { ...tool.params, defaultValue: tool.name }) : t(`architect.tools.${tool.name}`, { defaultValue: tool.name })}
                  </p>
                ))}
                {streaming ? (
                  <div className="max-w-full rounded-lg bg-muted px-3 py-2">
                    <MarkdownView text={streaming} bare small />
                  </div>
                ) : null}
              </div>
            </article>
          ) : null}
          {error ? (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <CircleAlert className="size-4" aria-hidden />
              {t(error, { defaultValue: t('architect.failed') })}
            </p>
          ) : null}
          <div ref={endRef} />
        </div>
      </div>
      {idleLeft !== null ? (
        <div className="flex items-center justify-between gap-2 border-t bg-warning/10 px-3 py-2 text-sm">
          <span>{t('architect.idle.warning', { seconds: idleLeft })}</span>
          <Button type="button" size="sm" variant="outline" onClick={onKeepAlive}>
            {t('architect.idle.keep')}
          </Button>
        </div>
      ) : null}
      {banner}
      <footer className="border-t p-2">
        <div className="flex items-end gap-2">
          <Textarea
            rows={2}
            value={draft}
            disabled={!active}
            placeholder={t(active ? 'architect.chat.placeholder' : 'architect.chat.startFirst')}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                send(draft);
              }
            }}
          />
          {sending ? (
            <Button type="button" variant="outline" onClick={onAbort}>
              <Square className="size-4" aria-hidden />
              {t('architect.chat.stop')}
            </Button>
          ) : (
            <Button type="button" onClick={() => send(draft)} disabled={!active || !draft.trim()}>
              <Send className="size-4" aria-hidden />
              {t('architect.chat.send')}
            </Button>
          )}
        </div>
      </footer>
    </div>
  );
}
