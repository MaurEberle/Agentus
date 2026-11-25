import { create } from 'zustand';
import type { TagMatch } from '@/lib/tags';
import type { HubFiles, HubHit, ModelKind } from '@/modules/models/model';

export type ModelsTab = 'installed' | 'hub';
export type InstalledSortKey = 'name' | 'size' | 'modified';
/** What the Hub sorts by; it sorts descending only. */
export type HubSort = 'downloads' | 'likes' | 'trending' | 'modified' | 'new';
/** Text: chat models, with or without vision (the Sehen capability decides). */
export type HubPipeline = 'text' | 'embed' | 'moe';
export type HubCapability = 'tools' | 'thinking' | 'vision';
/** A capability the model must have, or must not have; absent means either is fine. */
export type HubCapabilityRule = 'must' | 'never';
export type HubCapabilities = Partial<Record<HubCapability, HubCapabilityRule>>;

type InstalledUi = {
  search: string;
  sortKey: InstalledSortKey;
  sortDir: 'asc' | 'desc';
  kind: 'all' | ModelKind;
  tagFilter: string[];
  tagMode: TagMatch;
  selectedNames: string[];
  share: number;
  /** Which model cards are unfolded; kept while the user moves from model to model. */
  cardOpen: { own: boolean; base: boolean };
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
  retryAfter?: number;
};

export type HubFilesSnapshot = {
  id: string;
  data: HubFiles;
  /** `filesNonce` the data was fetched for; an older nonce means installed state may be stale. */
  nonce: number;
};

type HubUi = {
  search: string;
  debounced: string;
  pipelines: HubPipeline[];
  /** Parameter bounds in billions as typed; empty is open. `bounds` is what was searched. */
  minB: string;
  maxB: string;
  bounds: { min: string; max: string };
  sort: HubSort;
  pageSize: HubPageSize;
  capabilities: HubCapabilities;
  /** Minimum context window in tokens; 0 is any. */
  minContext: number;
  /** Leave out repos with a quant already pulled. */
  hideInstalled: boolean;
  /** Only models whose Q4_K_M fits the GPU. */
  fitsGpu: boolean;
  page: number;
  cursors: (string | null)[];
  picked: string | null;
  quant: string | null;
  share: number;
  snapshot: HubSnapshot | null;
  files: HubFilesSnapshot | null;
  filesError: string | null;
  /** Bumped when installed models change (download done, delete) so the picked files refetch. */
  filesNonce: number;
  /** Which model cards are unfolded; kept while the user moves from model to model. */
  cardOpen: { own: boolean; base: boolean };
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
  cardOpen: { own: true, base: false },
};

export const hubFilterDefaults: Pick<
  HubUi,
  'search' | 'debounced' | 'pipelines' | 'minB' | 'maxB' | 'bounds' | 'sort' | 'capabilities' | 'minContext' | 'hideInstalled' | 'fitsGpu'
> = {
  search: '',
  debounced: '',
  pipelines: [],
  minB: '',
  maxB: '',
  bounds: { min: '', max: '' },
  sort: 'downloads',
  capabilities: {},
  minContext: 0,
  hideInstalled: false,
  fitsGpu: false,
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
    filesNonce: 0,
    cardOpen: { own: true, base: false },
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

/** Hub detail lives in this store, not React Query: invalidate it explicitly. */
export function invalidateHubFiles(): void {
  useModelsUi.getState().patchHub((hub) => ({ filesNonce: hub.filesNonce + 1 }));
}
