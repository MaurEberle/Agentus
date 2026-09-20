import { create } from 'zustand';
import {
  helpChatSnapshot,
  type AppSettings,
  type HelpChatSettings,
  type HistoryRetentionDays,
} from '@/modules/settings/model';

export type RuntimeDraft = {
  ollamaBaseUrl: string;
  openaiCompatBaseUrl: string;
};

export type DataDraft = {
  historyRetentionDays: HistoryRetentionDays;
};

type SettingsDraftState = {
  runtime: RuntimeDraft | null;
  helpChat: HelpChatSettings | null;
  data: DataDraft | null;
  hydrate: (settings: AppSettings) => void;
  setRuntime: (patch: Partial<RuntimeDraft>) => void;
  setHelpChat: (patch: Partial<HelpChatSettings>) => void;
  setData: (patch: Partial<DataDraft>) => void;
  reset: (settings: AppSettings) => void;
  syncHelpChat: (settings: AppSettings) => void;
  syncRuntime: (settings: AppSettings) => void;
  syncData: (settings: AppSettings) => void;
  isDirty: (settings?: AppSettings | null) => boolean;
  runtimeDirty: (settings?: AppSettings | null) => boolean;
  helpDirty: (settings?: AppSettings | null) => boolean;
  dataDirty: (settings?: AppSettings | null) => boolean;
};

function runtimeFrom(settings: AppSettings): RuntimeDraft {
  return {
    ollamaBaseUrl: settings.ollamaBaseUrl,
    openaiCompatBaseUrl: settings.openaiCompatBaseUrl ?? '',
  };
}

function helpFrom(settings: AppSettings): HelpChatSettings {
  const help = settings.helpChat;
  return {
    provider: help.provider,
    model: help.model,
    credentialId: help.credentialId || undefined,
    embeddingProvider: help.embeddingProvider || '',
    embeddingModel: help.embeddingModel || '',
    webSearchEnabled: Boolean(help.webSearchEnabled),
    webSearchCredentialId: help.webSearchCredentialId || undefined,
    fallbackModel: help.fallbackModel || undefined,
  };
}

function dataFrom(settings: AppSettings): DataDraft {
  return { historyRetentionDays: settings.historyRetentionDays };
}

export const useSettingsDraft = create<SettingsDraftState>((set, get) => ({
  runtime: null,
  helpChat: null,
  data: null,
  hydrate: (settings) =>
    set({
      runtime: runtimeFrom(settings),
      helpChat: helpFrom(settings),
      data: dataFrom(settings),
    }),
  setRuntime: (patch) =>
    set((state) => ({
      runtime: { ...(state.runtime ?? { ollamaBaseUrl: '', openaiCompatBaseUrl: '' }), ...patch },
    })),
  setHelpChat: (patch) =>
    set((state) => ({
      helpChat: {
        ...(state.helpChat ?? {
          provider: '',
          model: '',
          webSearchEnabled: false,
        }),
        ...patch,
      },
    })),
  setData: (patch) =>
    set((state) => ({
      data: { ...(state.data ?? { historyRetentionDays: 90 }), ...patch },
    })),
  reset: (settings) =>
    set({
      runtime: runtimeFrom(settings),
      helpChat: helpFrom(settings),
      data: dataFrom(settings),
    }),
  syncHelpChat: (settings) => set({ helpChat: helpFrom(settings) }),
  syncRuntime: (settings) => set({ runtime: runtimeFrom(settings) }),
  syncData: (settings) => set({ data: dataFrom(settings) }),
  isDirty: (settings) => {
    const state = get();
    return state.runtimeDirty(settings) || state.helpDirty(settings) || state.dataDirty(settings);
  },
  runtimeDirty: (settings) => {
    if (!settings || !get().runtime) return false;
    return JSON.stringify(get().runtime) !== JSON.stringify(runtimeFrom(settings));
  },
  helpDirty: (settings) => {
    const help = get().helpChat;
    if (!settings || !help) return false;
    return helpChatSnapshot(help) !== helpChatSnapshot(helpFrom(settings));
  },
  dataDirty: (settings) => {
    if (!settings || !get().data) return false;
    return JSON.stringify(get().data) !== JSON.stringify(dataFrom(settings));
  },
}));
