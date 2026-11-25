import { create } from 'zustand';
import type { LlmProvider } from '@/modules/settings/model';

export type ModelPick = { provider: LlmProvider | ''; model: string; credentialId: string | null };

type ArchitectUi = {
  selectedId: string | null;
  /** Chat share of the width next to the brief and draft. */
  share: number;
  pick: ModelPick | null;
  select: (id: string | null) => void;
  setShare: (share: number) => void;
  setPick: (pick: ModelPick) => void;
};

export const useArchitectUi = create<ArchitectUi>((set) => ({
  selectedId: null,
  share: 0.55,
  pick: null,
  select: (selectedId) => set({ selectedId }),
  setShare: (share) => set({ share: Math.min(0.7, Math.max(0.35, share)) }),
  setPick: (pick) => set({ pick }),
}));
