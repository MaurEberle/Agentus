import { create } from 'zustand';
import type { LlmProvider } from '@/modules/settings/model';

export type ModelPick = { provider: LlmProvider | ''; model: string; credentialId: string | null };

type ArchitectUi = {
  selectedId: string | null;
  /** "Neu": an empty chat on purpose, not "nothing picked yet"; the page must not pick one for it. */
  fresh: boolean;
  /** Chat share of the width next to the brief and draft. */
  share: number;
  pick: ModelPick | null;
  /** Open entries of the brief accordion; they stay open across sessions. */
  briefOpen: string[];
  select: (id: string | null) => void;
  startNew: () => void;
  setShare: (share: number) => void;
  setPick: (pick: ModelPick) => void;
  setBriefOpen: (open: string[]) => void;
};

export const useArchitectUi = create<ArchitectUi>((set) => ({
  selectedId: null,
  fresh: false,
  share: 0.55,
  pick: null,
  briefOpen: ['goal'],
  select: (selectedId) => set({ selectedId, fresh: false }),
  startNew: () => set({ selectedId: null, fresh: true }),
  setShare: (share) => set({ share: Math.min(0.7, Math.max(0.35, share)) }),
  setPick: (pick) => set({ pick }),
  setBriefOpen: (briefOpen) => set({ briefOpen }),
}));
