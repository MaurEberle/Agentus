import { create } from 'zustand';
import type { LlmProvider } from '@/modules/settings/model';

export type ModelPick = { provider: LlmProvider | ''; model: string; credentialId: string | null };

/** Width of the session list in px, kept in this browser. */
export const SESSIONS_WIDTH = { min: 180, max: 520, initial: 240 } as const;
const SESSIONS_WIDTH_KEY = 'agentus.architect.sessionsWidth';

function clampSessionsWidth(value: number): number {
  return Math.round(Math.min(SESSIONS_WIDTH.max, Math.max(SESSIONS_WIDTH.min, value)));
}

function loadSessionsWidth(): number {
  try {
    const stored = Number(window.localStorage.getItem(SESSIONS_WIDTH_KEY));
    return Number.isFinite(stored) && stored > 0 ? clampSessionsWidth(stored) : SESSIONS_WIDTH.initial;
  } catch {
    return SESSIONS_WIDTH.initial;
  }
}

type ArchitectUi = {
  selectedId: string | null;
  /** "Neu": an empty chat on purpose, not "nothing picked yet"; the page must not pick one for it. */
  fresh: boolean;
  /** Chat share of the width next to the brief and draft. */
  share: number;
  sessionsWidth: number;
  pick: ModelPick | null;
  /** Open entries of the brief accordion; they stay open across sessions. */
  briefOpen: string[];
  select: (id: string | null) => void;
  startNew: () => void;
  setShare: (share: number) => void;
  setSessionsWidth: (width: number) => void;
  setPick: (pick: ModelPick) => void;
  setBriefOpen: (open: string[]) => void;
};

export const useArchitectUi = create<ArchitectUi>((set) => ({
  selectedId: null,
  fresh: false,
  share: 0.55,
  sessionsWidth: loadSessionsWidth(),
  pick: null,
  briefOpen: ['goal'],
  select: (selectedId) => set({ selectedId, fresh: false }),
  startNew: () => set({ selectedId: null, fresh: true }),
  setShare: (share) => set({ share: Math.min(0.7, Math.max(0.35, share)) }),
  setSessionsWidth: (width) => {
    const next = clampSessionsWidth(width);
    try {
      window.localStorage.setItem(SESSIONS_WIDTH_KEY, String(next));
    } catch {
      // Private window or blocked storage: the width just holds for this visit.
    }
    set({ sessionsWidth: next });
  },
  setPick: (pick) => set({ pick }),
  setBriefOpen: (briefOpen) => set({ briefOpen }),
}));
