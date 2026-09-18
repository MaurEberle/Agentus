import { create } from 'zustand';
import type { HelpSource } from '@/components/help-chat/model';

type HelpChatWidgetState = {
  generating: boolean;
  streamContent: string;
  streamSources: HelpSource[];
  errorKey?: string;
  errorMessage?: string;
  abort: (() => void) | null;
  startStream: (abort: () => void) => void;
  appendDelta: (chunk: string) => void;
  setSources: (sources: HelpSource[]) => void;
  finishStream: () => void;
  failStream: (error: { messageKey?: string; message?: string }) => void;
  clearError: () => void;
};

export const useHelpChatWidget = create<HelpChatWidgetState>((set) => ({
  generating: false,
  streamContent: '',
  streamSources: [],
  abort: null,
  startStream: (abort) =>
    set({
      generating: true,
      streamContent: '',
      streamSources: [],
      errorKey: undefined,
      errorMessage: undefined,
      abort,
    }),
  appendDelta: (chunk) => set((state) => ({ streamContent: state.streamContent + chunk })),
  setSources: (streamSources) => set({ streamSources }),
  finishStream: () =>
    set({
      generating: false,
      streamContent: '',
      streamSources: [],
      abort: null,
    }),
  failStream: (error) =>
    set({
      generating: false,
      abort: null,
      errorKey: error.messageKey,
      errorMessage: error.message,
    }),
  clearError: () => set({ errorKey: undefined, errorMessage: undefined }),
}));
