export type HelpChatUiStatus = 'unconfigured' | 'ready' | 'degraded' | 'generating' | 'error';

export type HelpChatStatus = {
  configured: boolean;
  onboardingSeen: boolean;
  webSearchEnabled?: boolean;
  degraded?: boolean;
};

export type HelpSource = {
  kind: 'rag' | 'web';
  title: string;
  section?: string;
  url?: string;
};

export type HelpMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
  sources?: HelpSource[];
};

export type HelpSendHandlers = {
  onDelta: (chunk: string) => void;
  onSources?: (sources: HelpSource[]) => void;
  onDone: (final: HelpMessage) => void;
  onError: (err: { messageKey?: string; message?: string }) => void;
};

export type HelpChatHandle = {
  getStatus(): Promise<HelpChatStatus>;
  setOnboardingSeen(): Promise<void>;
  listMessages(): Promise<HelpMessage[]>;
  send(text: string, handlers: HelpSendHandlers): { abort: () => void };
};

export const HELP_CHAT_MIN_WIDTH = 280;
export const HELP_CHAT_MIN_HEIGHT = 320;
/** Original panel `bottom-20` (80px). Extra FAB height is taken from panel height so the top edge stays put. */
export const HELP_CHAT_REF_BOTTOM = 80;

export function helpFabSize(viewport: { w: number; h: number }) {
  const scale = Math.min(viewport.w / 1280, viewport.h / 800);
  return Math.round(Math.min(80, Math.max(56, 64 * scale)));
}

export function helpChatAnchor(viewport: { w: number; h: number }) {
  const fab = helpFabSize(viewport);
  const inset = viewport.w >= 768 ? 24 : 16;
  return { fab, inset, bottom: inset + fab + 8, right: inset };
}

export function clampHelpChatSize(width: number, height: number, viewport: { w: number; h: number }) {
  const { bottom } = helpChatAnchor(viewport);
  const extra = Math.max(0, bottom - HELP_CHAT_REF_BOTTOM);
  const fitH = Math.max(160, viewport.h - bottom - 16);
  const maxH = Math.min(viewport.h * 0.8 - extra, fitH);
  const maxW = Math.max(HELP_CHAT_MIN_WIDTH, viewport.w * 0.3);
  const minH = Math.min(HELP_CHAT_MIN_HEIGHT, maxH);
  return {
    width: Math.min(Math.max(width, HELP_CHAT_MIN_WIDTH), maxW),
    height: Math.min(Math.max(height, minH), maxH),
  };
}

export function defaultHelpChatSize(viewport: { w: number; h: number }) {
  return clampHelpChatSize(viewport.w * 0.3, viewport.h * 0.8, viewport);
}

export function deriveHelpStatus(input: {
  configured: boolean;
  generating: boolean;
  error: boolean;
  degraded?: boolean;
}): HelpChatUiStatus {
  if (input.generating) return 'generating';
  if (input.error) return 'error';
  if (!input.configured) return 'unconfigured';
  if (input.degraded) return 'degraded';
  return 'ready';
}
