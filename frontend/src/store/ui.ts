import type { StateCreator } from 'zustand';
import type { AppStore } from '@/store/types';

export interface UiSlice {
  helpChatFabVisible: boolean;
  helpChatOpen: boolean;
  sidebarCollapsed: boolean;
  windowMaximized: boolean;
  setHelpChatFabVisible: (visible: boolean) => void;
  setHelpChatOpen: (open: boolean) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setWindowMaximized: (maximized: boolean) => void;
}

export const createUiSlice: StateCreator<AppStore, [], [], UiSlice> = (set) => ({
  helpChatFabVisible: true,
  helpChatOpen: false,
  sidebarCollapsed: false,
  windowMaximized: false,
  setHelpChatFabVisible: (helpChatFabVisible) => set({ helpChatFabVisible }),
  setHelpChatOpen: (helpChatOpen) => set({ helpChatOpen }),
  setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setWindowMaximized: (windowMaximized) => set({ windowMaximized }),
});
