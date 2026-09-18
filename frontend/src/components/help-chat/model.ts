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

export function clampHelpChatSize(width: number, height: number, viewport: { w: number; h: number }) {
  return {
    width: Math.min(Math.max(width, HELP_CHAT_MIN_WIDTH), Math.max(HELP_CHAT_MIN_WIDTH, viewport.w * 0.5)),
    height: Math.min(Math.max(height, HELP_CHAT_MIN_HEIGHT), Math.max(HELP_CHAT_MIN_HEIGHT, viewport.h * 0.8)),
  };
}

export function defaultHelpChatSize(viewport: { w: number; h: number }) {
  return clampHelpChatSize(viewport.w * 0.2, Math.max(HELP_CHAT_MIN_HEIGHT, viewport.h * 0.45), viewport);
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
