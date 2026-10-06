import { useCallback, useState } from 'react';
import {
  clampPaneHeight,
  clampPaneShare,
  PANE_MAX_SHARE,
  PANE_MIN_SHARE,
} from '@/modules/monitoring/panes';

const STORAGE_KEY = 'agentus.history.panes';

export type HistoryPanes = {
  chartH: number;
  errorsH: number;
  statsShare: number;
  listH: number;
  detailH: number;
  listShare: number;
};

export const DEFAULT_HISTORY_PANES: HistoryPanes = {
  chartH: 280,
  errorsH: 280,
  statsShare: 0.5,
  listH: 480,
  detailH: 560,
  listShare: 0.5,
};

function clampHistoryShare(value: number, fallback: number): number {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(PANE_MAX_SHARE, Math.max(PANE_MIN_SHARE, value));
}

export function normalizeHistoryPanes(raw: Partial<HistoryPanes> | null | undefined): HistoryPanes {
  return {
    chartH: clampPaneHeight(Number(raw?.chartH) || DEFAULT_HISTORY_PANES.chartH),
    errorsH: clampPaneHeight(Number(raw?.errorsH) || DEFAULT_HISTORY_PANES.errorsH),
    statsShare: clampHistoryShare(Number(raw?.statsShare), DEFAULT_HISTORY_PANES.statsShare),
    listH: clampPaneHeight(Number(raw?.listH) || DEFAULT_HISTORY_PANES.listH),
    detailH: clampPaneHeight(Number(raw?.detailH) || DEFAULT_HISTORY_PANES.detailH),
    listShare: clampHistoryShare(Number(raw?.listShare), DEFAULT_HISTORY_PANES.listShare),
  };
}

export function loadHistoryPanes(): HistoryPanes {
  if (typeof window === 'undefined') return { ...DEFAULT_HISTORY_PANES };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_HISTORY_PANES };
    return normalizeHistoryPanes(JSON.parse(raw) as Partial<HistoryPanes>);
  } catch {
    return { ...DEFAULT_HISTORY_PANES };
  }
}

export function saveHistoryPanes(panes: HistoryPanes): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizeHistoryPanes(panes)));
  } catch {
    /* quota */
  }
}

export function useHistoryPanes() {
  const [panes, setPanes] = useState(loadHistoryPanes);

  const update = useCallback((patch: Partial<HistoryPanes>) => {
    setPanes((prev) => {
      const next = normalizeHistoryPanes({
        ...prev,
        ...patch,
        chartH: patch.chartH != null ? clampPaneHeight(patch.chartH) : prev.chartH,
        errorsH: patch.errorsH != null ? clampPaneHeight(patch.errorsH) : prev.errorsH,
        statsShare: patch.statsShare != null ? clampPaneShare(patch.statsShare) : prev.statsShare,
        listH: patch.listH != null ? clampPaneHeight(patch.listH) : prev.listH,
        detailH: patch.detailH != null ? clampPaneHeight(patch.detailH) : prev.detailH,
        listShare: patch.listShare != null ? clampPaneShare(patch.listShare) : prev.listShare,
      });
      saveHistoryPanes(next);
      return next;
    });
  }, []);

  return [panes, update] as const;
}
