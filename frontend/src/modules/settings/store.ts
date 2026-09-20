import { create } from 'zustand';
import type { AppSettings, HelpChatSettings, HistoryRetentionDays } from '@/modules/settings/model';

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
    embeddingProvider: help.embeddingProvider,
    embeddingModel: help.embeddingModel,
    webSearchEnabled: help.webSearchEnabled,
    webSearchCredentialId: help.webSearchCredentialId || undefined,
    fallbackModel: help.fallbackModel,
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
  isDirty: (settings) => {
    const state = get();
    return state.runtimeDirty(settings) || state.helpDirty(settings) || state.dataDirty(settings);
  },
  runtimeDirty: (settings) => {
    if (!settings || !get().runtime) return false;
    return JSON.stringify(get().runtime) !== JSON.stringify(runtimeFrom(settings));
  },
  helpDirty: (settings) => {
    if (!settings || !get().helpChat) return false;
    return JSON.stringify(get().helpChat) !== JSON.stringify(helpFrom(settings));
  },
  dataDirty: (settings) => {
    if (!settings || !get().data) return false;
    return JSON.stringify(get().data) !== JSON.stringify(dataFrom(settings));
  },
}));
