import { create } from 'zustand';

export type NetworksSortKey = 'name' | 'updatedAt' | 'lastUsedAt';
export type NetworksSortDir = 'asc' | 'desc';

type NetworksUiStore = {
  selectedIds: string[];
  anchorId: string | null;
  query: string;
  sortKey: NetworksSortKey;
  sortDir: NetworksSortDir;
  tagFilter: string[];
  onlyValid: boolean;
  onlyActive: boolean;
  setQuery: (query: string) => void;
  setSortKey: (key: NetworksSortKey) => void;
  toggleSortDir: () => void;
  toggleTag: (tag: string) => void;
  setOnlyValid: (value: boolean) => void;
  setOnlyActive: (value: boolean) => void;
  select: (ids: string[], anchorId?: string | null) => void;
  clearSelection: () => void;
  pruneSelection: (existingIds: string[]) => void;
};

function sameIds(a: string[], b: string[]) {
  return a.length === b.length && a.every((id, index) => id === b[index]);
}

export const useNetworksUi = create<NetworksUiStore>((set, get) => ({
  selectedIds: [],
  anchorId: null,
  query: '',
  sortKey: 'updatedAt',
  sortDir: 'desc',
  tagFilter: [],
  onlyValid: false,
  onlyActive: false,
  setQuery: (query) => set({ query }),
  setSortKey: (sortKey) =>
    set((state) => ({
      sortKey,
      sortDir: state.sortKey === sortKey ? (state.sortDir === 'asc' ? 'desc' : 'asc') : 'desc',
    })),
  toggleSortDir: () => set((state) => ({ sortDir: state.sortDir === 'asc' ? 'desc' : 'asc' })),
  toggleTag: (tag) =>
    set((state) => ({
      tagFilter: state.tagFilter.includes(tag)
        ? state.tagFilter.filter((item) => item !== tag)
        : [...state.tagFilter, tag],
    })),
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
