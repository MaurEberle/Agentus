import { create } from 'zustand';

/**
 * Which stored version the editor shows read-only instead of the working document, and whether
 * the versions dialog is open. The inspector's picker sets it; the editor renders it.
 */
type VersionPreviewState = {
  preview: { networkId: string; version: number } | null;
  dialogOpen: boolean;
  /** ``null`` returns to the working document. */
  setPreview: (networkId: string, version: number | null) => void;
  clearPreview: () => void;
  setDialogOpen: (open: boolean) => void;
};

export const useVersionPreview = create<VersionPreviewState>((set) => ({
  preview: null,
  dialogOpen: false,
  setPreview: (networkId, version) => set({ preview: version === null ? null : { networkId, version } }),
  clearPreview: () => set({ preview: null }),
  setDialogOpen: (open) => set({ dialogOpen: open }),
}));
