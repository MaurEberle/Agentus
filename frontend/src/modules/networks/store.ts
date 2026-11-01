import { create } from 'zustand';
import type { TagMatch } from '@/lib/tags';

export type NetworksSortKey = 'name' | 'updatedAt' | 'lastUsedAt';
export type NetworksSortDir = 'asc' | 'desc';

const FILTER_KEY = 'agentus.networks.filters';
const SORT_KEYS: NetworksSortKey[] = ['name', 'updatedAt', 'lastUsedAt'];

type NetworkFilters = {
  query: string;
  sortKey: NetworksSortKey;
  sortDir: NetworksSortDir;
  tagFilter: string[];
  tagMode: TagMatch;
  onlyValid: boolean;
  onlyActive: boolean;
};

const FILTER_DEFAULTS: NetworkFilters = {
  query: '',
  sortKey: 'updatedAt',
  sortDir: 'desc',
  tagFilter: [],
  tagMode: 'or',
  onlyValid: false,
  onlyActive: false,
};

function normalizeFilters(raw: Partial<NetworkFilters> | null | undefined): NetworkFilters {
  const sortKey = SORT_KEYS.includes(raw?.sortKey as NetworksSortKey) ? (raw?.sortKey as NetworksSortKey) : FILTER_DEFAULTS.sortKey;
  const sortDir = raw?.sortDir === 'asc' || raw?.sortDir === 'desc' ? raw.sortDir : FILTER_DEFAULTS.sortDir;
  const tagMode = raw?.tagMode === 'and' || raw?.tagMode === 'or' ? raw.tagMode : FILTER_DEFAULTS.tagMode;
  const tagFilter = Array.isArray(raw?.tagFilter) ? raw.tagFilter.filter((tag) => typeof tag === 'string' && tag.trim()) : [];
  return {
    query: typeof raw?.query === 'string' ? raw.query : '',
    sortKey,
    sortDir,
    tagFilter,
    tagMode,
    onlyValid: raw?.onlyValid === true,
    onlyActive: raw?.onlyActive === true,
  };
}

function loadFilters(): NetworkFilters {
  try {
    const raw = window.localStorage.getItem(FILTER_KEY);
    if (!raw) return { ...FILTER_DEFAULTS, tagFilter: [] };
    return normalizeFilters(JSON.parse(raw) as Partial<NetworkFilters>);
  } catch {
    return { ...FILTER_DEFAULTS, tagFilter: [] };
  }
}

function saveFilters(filters: NetworkFilters): void {
  try {
    window.localStorage.setItem(FILTER_KEY, JSON.stringify(normalizeFilters(filters)));
  } catch {
    // Remembering the filters is optional.
  }
}

function filterOf(state: NetworkFilters): NetworkFilters {
  return {
    query: state.query,
    sortKey: state.sortKey,
    sortDir: state.sortDir,
    tagFilter: state.tagFilter,
    tagMode: state.tagMode,
    onlyValid: state.onlyValid,
    onlyActive: state.onlyActive,
  };
}

type NetworksUiStore = {
  selectedIds: string[];
  anchorId: string | null;
  query: string;
  sortKey: NetworksSortKey;
  sortDir: NetworksSortDir;
  tagFilter: string[];
  tagMode: TagMatch;
  onlyValid: boolean;
  onlyActive: boolean;
  setQuery: (query: string) => void;
  setSortKey: (key: NetworksSortKey) => void;
  toggleSortDir: () => void;
  toggleTag: (tag: string) => void;
  clearTags: () => void;
  setTagMode: (mode: TagMatch) => void;
  setOnlyValid: (value: boolean) => void;
  setOnlyActive: (value: boolean) => void;
  select: (ids: string[], anchorId?: string | null) => void;
  clearSelection: () => void;
  pruneSelection: (existingIds: string[]) => void;
};

function sameIds(a: string[], b: string[]) {
  return a.length === b.length && a.every((id, index) => id === b[index]);
}

const storedFilters = loadFilters();

export const useNetworksUi = create<NetworksUiStore>((set, get) => ({
  selectedIds: [],
  anchorId: null,
  query: storedFilters.query,
  sortKey: storedFilters.sortKey,
  sortDir: storedFilters.sortDir,
  tagFilter: storedFilters.tagFilter,
  tagMode: storedFilters.tagMode,
  onlyValid: storedFilters.onlyValid,
  onlyActive: storedFilters.onlyActive,
  setQuery: (query) => set({ query }),
  setSortKey: (sortKey) =>
    set((state) => ({
      sortKey,
      sortDir:
        state.sortKey === sortKey
          ? state.sortDir === 'asc'
            ? 'desc'
            : 'asc'
          : sortKey === 'name'
            ? 'asc'
            : 'desc',
    })),
  toggleSortDir: () => set((state) => ({ sortDir: state.sortDir === 'asc' ? 'desc' : 'asc' })),
  toggleTag: (tag) =>
    set((state) => ({
      tagFilter: state.tagFilter.includes(tag)
        ? state.tagFilter.filter((item) => item !== tag)
        : [...state.tagFilter, tag],
    })),
  clearTags: () => set({ tagFilter: [] }),
  setTagMode: (tagMode) => set({ tagMode }),
  setOnlyValid: (onlyValid) => set({ onlyValid }),
  setOnlyActive: (onlyActive) => set({ onlyActive }),
  select: (selectedIds, anchorId) => {
    const current = get();
    const nextAnchor = anchorId === undefined ? current.anchorId : anchorId;
    if (sameIds(current.selectedIds, selectedIds) && current.anchorId === nextAnchor) return;
    set({ selectedIds, anchorId: nextAnchor });
  },
  clearSelection: () => {
    const current = get();
    if (current.selectedIds.length === 0 && current.anchorId === null) return;
    set({ selectedIds: [], anchorId: null });
  },
  pruneSelection: (existingIds) => {
    const allowed = new Set(existingIds);
    const current = get();
    const selectedIds = current.selectedIds.filter((id) => allowed.has(id));
    const anchorId =
      current.anchorId && allowed.has(current.anchorId) ? current.anchorId : (selectedIds[0] ?? null);
    if (sameIds(current.selectedIds, selectedIds) && current.anchorId === anchorId) return;
    set({ selectedIds, anchorId });
  },
}));

let rememberedFilters = JSON.stringify(filterOf(useNetworksUi.getState()));
useNetworksUi.subscribe((state) => {
  const next = JSON.stringify(filterOf(state));
  if (next === rememberedFilters) return;
  rememberedFilters = next;
  saveFilters(filterOf(state));
});
