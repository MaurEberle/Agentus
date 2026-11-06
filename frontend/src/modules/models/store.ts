import { create } from 'zustand';
import type { TagMatch } from '@/lib/tags';
import type { HubFiles, HubHit, ModelKind } from '@/modules/models/model';

export type ModelsTab = 'installed' | 'hub';
export type InstalledSortKey = 'name' | 'size' | 'modified';
export type HubSort = 'downloads' | 'likes' | 'trending' | 'modified' | 'name';
export type HubPipeline = 'text' | 'embed' | 'vision' | 'moe';
export type HubSize = 'any' | '3' | '8' | '14' | '32' | '70' | 'xl' | 'custom';
export type HubCapability = 'tools' | 'thinking' | 'vision';

type InstalledUi = {
  search: string;
  sortKey: InstalledSortKey;
  sortDir: 'asc' | 'desc';
  kind: 'all' | ModelKind;
  tagFilter: string[];
  tagMode: TagMatch;
  selectedNames: string[];
  share: number;
};

export const HUB_PAGE_SIZES = [10, 20, 30, 50, 100] as const;
export type HubPageSize = (typeof HUB_PAGE_SIZES)[number];

const PAGE_SIZE_KEY = 'agentus.models.hubPageSize';

export function loadHubPageSize(): HubPageSize {
  try {
    const value = Number(window.localStorage.getItem(PAGE_SIZE_KEY));
    if ((HUB_PAGE_SIZES as readonly number[]).includes(value)) return value as HubPageSize;
  } catch {
    // Storage can be blocked. The default page size still works.
  }
  return 30;
}

export function rememberHubPageSize(value: number): void {
  try {
    window.localStorage.setItem(PAGE_SIZE_KEY, String(value));
  } catch {
    // Remembering the page size is optional.
  }
}

export type HubSnapshot = {
  key: string;
  items: HubHit[];
  hasNext: boolean;
  nextCursor?: string;
  errorKey?: string;
};

export type HubFilesSnapshot = {
  id: string;
  data: HubFiles;
};

type HubUi = {
  search: string;
  debounced: string;
  pipelines: HubPipeline[];
  size: HubSize;
  minB: string;
  maxB: string;
  bounds: { min: string; max: string };
  sort: HubSort;
  sortDir: 'asc' | 'desc';
  pageSize: HubPageSize;
  capabilities: HubCapability[];
  page: number;
  cursors: (string | null)[];
  picked: string | null;
  quant: string | null;
  share: number;
  snapshot: HubSnapshot | null;
  files: HubFilesSnapshot | null;
  filesError: string | null;
};

type ModelsUiStore = {
  tab: ModelsTab;
  installed: InstalledUi;
  hub: HubUi;
  setTab: (tab: ModelsTab) => void;
  patchInstalled: (patch: Partial<InstalledUi> | ((current: InstalledUi) => Partial<InstalledUi>)) => void;
  patchHub: (patch: Partial<HubUi> | ((current: HubUi) => Partial<HubUi>)) => void;
  resetHubFilters: () => void;
};

const installedDefaults: InstalledUi = {
  search: '',
  sortKey: 'name',
  sortDir: 'asc',
  kind: 'all',
  tagFilter: [],
  tagMode: 'or',
  selectedNames: [],
  share: 0.62,
};

export const hubFilterDefaults: Pick<HubUi, 'search' | 'debounced' | 'pipelines' | 'size' | 'minB' | 'maxB' | 'bounds' | 'sort' | 'sortDir' | 'capabilities'> = {
  search: '',
  debounced: '',
  pipelines: [],
  size: 'any',
  minB: '',
  maxB: '',
  bounds: { min: '', max: '' },
  sort: 'downloads',
  sortDir: 'desc',
  capabilities: [],
};

export const useModelsUi = create<ModelsUiStore>((set) => ({
  tab: 'installed',
  installed: installedDefaults,
  hub: {
    ...hubFilterDefaults,
    pageSize: loadHubPageSize(),
    page: 0,
    cursors: [null],
    picked: null,
    quant: null,
    share: 0.68,
    snapshot: null,
    files: null,
    filesError: null,
  },
  setTab: (tab) => set({ tab }),
  patchInstalled: (patch) =>
    set((state) => ({
      installed: { ...state.installed, ...(typeof patch === 'function' ? patch(state.installed) : patch) },
    })),
  patchHub: (patch) =>
    set((state) => {
      const next = typeof patch === 'function' ? patch(state.hub) : patch;
      if (next === state.hub) return state;
      return { hub: { ...state.hub, ...next } };
    }),
  resetHubFilters: () =>
    set((state) => ({
      hub: { ...state.hub, ...hubFilterDefaults, page: 0, cursors: [null] },
    })),
}));
