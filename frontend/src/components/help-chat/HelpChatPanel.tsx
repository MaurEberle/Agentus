import { useCallback, useEffect, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { Link } from 'react-router-dom';
import { Settings, Square, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { HelpChatMessages } from '@/components/help-chat/HelpChatMessages';
import { sendHelpMessage, useHelpMessagesQuery } from '@/components/help-chat/api';
import {
  clampHelpChatSize,
  defaultHelpChatSize,
  deriveHelpStatus,
  type HelpChatStatus,
  type HelpMessage,
} from '@/components/help-chat/model';
import { useHelpChatWidget } from '@/components/help-chat/store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useFocusTrap } from '@/hooks/useFocusTrap';
import { notify } from '@/lib/notifications';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';

export function HelpChatPanel({
  compact,
  status,
  onClose,
}: {
  compact: boolean;
  status: HelpChatStatus | undefined;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const panelRef = useRef<HTMLDivElement>(null);
  const width = useAppStore((state) => state.helpChatWidth);
  const height = useAppStore((state) => state.helpChatHeight);
  const setHelpChatSize = useAppStore((state) => state.setHelpChatSize);
  const { data: messages = [] } = useHelpMessagesQuery();
  const generating = useHelpChatWidget((state) => state.generating);
  const streamContent = useHelpChatWidget((state) => state.streamContent);
  const streamSources = useHelpChatWidget((state) => state.streamSources);
  const pendingUser = useHelpChatWidget((state) => state.pendingUser);
  const pendingBaseCount = useHelpChatWidget((state) => state.pendingBaseCount);
  const errorKey = useHelpChatWidget((state) => state.errorKey);
  const errorMessage = useHelpChatWidget((state) => state.errorMessage);
  const abort = useHelpChatWidget((state) => state.abort);
  const [draft, setDraft] = useState('');

  const configured = Boolean(status?.configured);
  const uiStatus = deriveHelpStatus({
    configured,
    generating,
    error: Boolean(errorKey || errorMessage),
    degraded: status?.degraded,
  });
  const canSend =
    configured &&
    !generating &&
    (uiStatus === 'ready' || uiStatus === 'degraded' || uiStatus === 'error') &&
    draft.trim().length > 0;

  const onEscape = useCallback(() => onClose(), [onClose]);
  useFocusTrap(!compact, panelRef, onEscape);

  useLayoutEffect(() => {
    if (compact) return;
    setHelpChatSize(defaultHelpChatSize({ w: window.innerWidth, h: window.innerHeight }));
  }, [compact, setHelpChatSize]);

  function startResize(edge: 'left' | 'top' | 'corner') {
    return (event: ReactPointerEvent<HTMLDivElement>) => {
      event.preventDefault();
      const startX = event.clientX;
      const startY = event.clientY;
      const startW = width || window.innerWidth * 0.3;
      const startH = height || window.innerHeight * 0.8;
      function move(moveEvent: PointerEvent) {
        const viewport = { w: window.innerWidth, h: window.innerHeight };
        const dw = edge === 'top' ? 0 : startX - moveEvent.clientX;
        const dh = edge === 'left' ? 0 : startY - moveEvent.clientY;
        setHelpChatSize(clampHelpChatSize(startW + dw, startH + dh, viewport));
      }
      function up() {
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
      }
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    };
  }

  function send() {
    const text = draft.trim();
    if (!canSend) return;
    setDraft('');
    useHelpChatWidget.getState().clearError();
    useHelpChatWidget.getState().setPendingUser(
      {
        id: `pending-${Date.now()}`,
        role: 'user',
        content: text,
        createdAt: new Date().toISOString(),
      },
      messages.length,
    );
    const handle = sendHelpMessage(text, {
      onDelta: (chunk) => useHelpChatWidget.getState().appendDelta(chunk),
      onSources: (sources) => useHelpChatWidget.getState().setSources(sources),
      onDone: () => useHelpChatWidget.getState().finishStream(),
      onError: (error) => {
        useHelpChatWidget.getState().failStream(error);
        notify({
          titleKey: error.messageKey ?? 'helpChat.error.generic',
          variant: 'error',
        });
      },
    });
    useHelpChatWidget.getState().startStream(handle.abort);
  }

  useEffect(() => {
    if (pendingUser && messages.length > pendingBaseCount) {
      useHelpChatWidget.getState().clearPendingUser();
    }
  }, [messages.length, pendingBaseCount, pendingUser]);

  const visibleMessages =
    pendingUser && messages.length <= pendingBaseCount ? [...messages, pendingUser] : messages;

  const streaming: HelpMessage | null =
    generating && streamContent
      ? {
          id: 'streaming',
          role: 'assistant',
          content: streamContent,
          createdAt: new Date().toISOString(),
          sources: streamSources,
        }
      : null;

  return (
    <div
      ref={panelRef}
      className={cn(
        'app-no-drag relative flex flex-col overflow-hidden border bg-background shadow-xl',
        compact ? 'h-full rounded-none' : 'rounded-xl',
      )}
      style={
        compact
          ? undefined
          : {
              width,
              height,
              minWidth: 280,
              minHeight: 320,
              maxWidth: '30vw',
              maxHeight: '80vh',
            }
      }
      role="dialog"
      aria-label={t('helpChat.title')}
    >
      {!compact ? (
        <>
          <div
            className="absolute left-0 top-0 z-10 h-3 w-3 cursor-nwse-resize"
            onPointerDown={startResize('corner')}
            aria-hidden
          />
          <div
            className="absolute left-0 top-3 z-10 h-[calc(100%-0.75rem)] w-1.5 cursor-ew-resize"
            onPointerDown={startResize('left')}
            aria-label={t('helpChat.resize.width')}
            role="separator"
          />
          <div
            className="absolute left-3 top-0 z-10 h-1.5 w-[calc(100%-0.75rem)] cursor-ns-resize"
            onPointerDown={startResize('top')}
            aria-label={t('helpChat.resize.height')}
            role="separator"
          />
        </>
      ) : null}
      <header className="relative flex items-center gap-2 border-b px-3 py-2">
        <h2 className="min-w-0 flex-1 truncate text-sm font-semibold">{t('helpChat.title')}</h2>
        <Badge variant={uiStatus === 'error' || uiStatus === 'unconfigured' ? 'secondary' : 'default'}>
          {t(`helpChat.status.${uiStatus}`)}
        </Badge>
        <Button variant="ghost" size="icon" asChild>
          <Link to="/settings#help-chat" aria-label={t('helpChat.action.settings')}>
            <Settings className="size-4" />
          </Link>
        </Button>
        <Button type="button" variant="ghost" size="icon" onClick={onClose} aria-label={t('helpChat.action.close')}>
          <X className="size-4" />
        </Button>
      </header>
      {!configured ? (
        <div className="flex flex-1 flex-col items-start justify-center gap-3 p-4">
          <p className="text-sm text-muted-foreground">{t('helpChat.unconfigured.body')}</p>
          <Button asChild>
            <Link to="/settings#help-chat">{t('helpChat.unconfigured.cta')}</Link>
          </Button>
        </div>
      ) : (
        <HelpChatMessages
          messages={visibleMessages}
          streaming={streaming}
          waiting={generating && !streamContent}
        />
      )}
      {errorKey || errorMessage ? (
        <p className="px-3 text-xs text-destructive">
          {errorMessage ?? t(errorKey ?? 'helpChat.error.generic')}
        </p>
      ) : null}
      <footer className="border-t p-2">
        <div className="flex items-end gap-2">
          <Textarea
            rows={2}
            value={draft}
            disabled={!configured || generating}
            placeholder={t('helpChat.input.placeholder')}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                send();
              }
            }}
          />
          {generating ? (
            <Button type="button" variant="outline" onClick={() => abort?.()} aria-label={t('helpChat.action.stop')}>
              <Square className="size-4" />
              {t('helpChat.action.stop')}
            </Button>
          ) : (
            <Button type="button" onClick={send} disabled={!canSend}>
              {t('helpChat.action.send')}
            </Button>
          )}
        </div>
      </footer>
    </div>
  );
}
