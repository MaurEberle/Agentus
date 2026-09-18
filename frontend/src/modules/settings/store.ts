import { create } from 'zustand';
import { defaultSettings, type AppSettings, type HelpChatSettings, type HistoryRetentionDays } from '@/modules/settings/model';

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

function dataFrom(settings: AppSettings): DataDraft {
  return { historyRetentionDays: settings.historyRetentionDays };
}

const initial = defaultSettings();

export const useSettingsDraft = create<SettingsDraftState>((set, get) => ({
  runtime: runtimeFrom(initial),
  helpChat: { ...initial.helpChat },
  data: dataFrom(initial),
  hydrate: (settings) =>
    set({
      runtime: runtimeFrom(settings),
      helpChat: { ...settings.helpChat },
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
      helpChat: { ...settings.helpChat },
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
    return JSON.stringify(get().helpChat) !== JSON.stringify(settings.helpChat);
  },
  dataDirty: (settings) => {
    if (!settings || !get().data) return false;
    return JSON.stringify(get().data) !== JSON.stringify(dataFrom(settings));
  },
}));
