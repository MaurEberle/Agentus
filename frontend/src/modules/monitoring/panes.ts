const STORAGE_KEY = 'agentus.monitoring.panes';

export const PANE_MIN_H = 256;
export const PANE_MAX_H = 1000;
export const PANE_MIN_SHARE = 0.28;
export const PANE_MAX_SHARE = 0.72;

export type MonitoringPanes = {
  chatH: number;
  graphH: number;
  activityH: number;
  graphShare: number;
};

export const DEFAULT_PANES: MonitoringPanes = {
  chatH: 400,
  graphH: 320,
  activityH: 280,
  graphShare: 0.58,
};

export function clampPaneHeight(value: number): number {
  if (!Number.isFinite(value)) return PANE_MIN_H;
  return Math.min(PANE_MAX_H, Math.max(PANE_MIN_H, Math.round(value)));
}

export function clampPaneShare(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_PANES.graphShare;
  return Math.min(PANE_MAX_SHARE, Math.max(PANE_MIN_SHARE, value));
}

export function normalizePanes(raw: Partial<MonitoringPanes> | null | undefined): MonitoringPanes {
  return {
    chatH: clampPaneHeight(Number(raw?.chatH) || DEFAULT_PANES.chatH),
    graphH: clampPaneHeight(Number(raw?.graphH) || DEFAULT_PANES.graphH),
    activityH: clampPaneHeight(Number(raw?.activityH) || DEFAULT_PANES.activityH),
    graphShare: clampPaneShare(Number(raw?.graphShare) || DEFAULT_PANES.graphShare),
  };
}

export function loadPanes(): MonitoringPanes {
  if (typeof window === 'undefined') return { ...DEFAULT_PANES };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PANES };
    return normalizePanes(JSON.parse(raw) as Partial<MonitoringPanes>);
  } catch {
    return { ...DEFAULT_PANES };
  }
}

export function savePanes(panes: MonitoringPanes): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizePanes(panes)));
  } catch {
    /* quota */
  }
}
