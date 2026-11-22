import { create } from 'zustand';
import type { DetailTab } from '@/modules/history/model/types';
import type { LogView } from '@/modules/monitoring/model/logView';

type HistoryUi = {
  selectedIds: string[];
  anchorId: string | null;
  detailTab: DetailTab;
  logView: LogView;
  logQuery: string;
  logNodeId: string | null;
  logErrorsOnly: boolean;
  selectedLogId: string | null;
  select: (ids: string[], anchorId?: string | null) => void;
  clearSelection: () => void;
  pruneSelection: (existingIds: string[]) => void;
  setDetailTab: (tab: DetailTab) => void;
  setLogView: (view: LogView) => void;
  setLogQuery: (query: string) => void;
  setLogNodeId: (id: string | null) => void;
  setLogErrorsOnly: (value: boolean) => void;
  setSelectedLogId: (id: string | null) => void;
};

function sameIds(a: string[], b: string[]) {
  return a.length === b.length && a.every((id, index) => id === b[index]);
}

export const useHistoryUi = create<HistoryUi>((set, get) => ({
  selectedIds: [],
  anchorId: null,
  detailTab: 'log',
  logView: 'important',
  logQuery: '',
  logNodeId: null,
  logErrorsOnly: false,
  selectedLogId: null,
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
  setDetailTab: (detailTab) => set({ detailTab }),
  setLogView: (logView) => set({ logView }),
  setLogQuery: (logQuery) => set({ logQuery }),
  setLogNodeId: (logNodeId) => set({ logNodeId }),
  setLogErrorsOnly: (logErrorsOnly) => set({ logErrorsOnly }),
  setSelectedLogId: (selectedLogId) => set({ selectedLogId }),
}));
