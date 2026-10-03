import i18n from '@/i18n';
import { getChromeHost } from '@/lib/chromeHost';
import { notify } from '@/lib/notifications';
import { useAppStore, type WaitAsk } from '@/store';

export const WAIT_ASK_ACTION = 'open-run-chat';

let openChat: (() => void) | null = null;
let monitoringTab: 'chat' | 'log' = 'log';

export function registerWaitAskOpen(fn: (() => void) | null) {
  openChat = fn;
  return () => {
    if (openChat === fn) openChat = null;
  };
}

export function hintMonitoringTab(tab: 'chat' | 'log') {
  monitoringTab = tab;
}

export function waitAskKey(ask: WaitAsk | null | undefined): string {
  return ask?.id ?? '';
}

export function speakerLabel(speaker: string): string {
  const trimmed = speaker.trim();
  if (!trimmed) return i18n.t('monitoring.nodeType.orchestrator');
  const key = `monitoring.nodeType.${trimmed}`;
  return i18n.exists(key) ? i18n.t(key) : trimmed;
}

function shouldToastWaitAsk(): boolean {
  if (typeof window === 'undefined' || typeof document === 'undefined') return true;
  const onChat =
    window.location.pathname.startsWith('/monitoring') && monitoringTab === 'chat';
  return !(onChat && document.hasFocus() && document.visibilityState === 'visible');
}

export function applyWaitAsk(next: WaitAsk | null) {
  const prev = useAppStore.getState().waitAsk;
  if (waitAskKey(prev) === waitAskKey(next)) return;
  useAppStore.getState().setWaitAsk(next);
  if (next) {
    notify({
      titleKey: 'notify.waitAsk.title',
      descriptionKey: next.excerpt ? 'notify.waitAsk.desc' : 'monitoring.chat.waitReply',
      values: { speaker: speakerLabel(next.speaker), excerpt: next.excerpt },
      variant: 'warning',
      action: WAIT_ASK_ACTION,
      duration: Number.POSITIVE_INFINITY,
      toast: shouldToastWaitAsk(),
    });
    void getChromeHost()?.requestAttention?.(true);
  } else {
    void getChromeHost()?.requestAttention?.(false);
  }
}

export function openRunChat() {
  openChat?.();
  void getChromeHost()?.requestAttention?.(false);
}
