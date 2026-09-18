import type { StateCreator } from 'zustand';
import type { AppStore } from '@/store/types';

export interface UiSlice {
  helpChatFabVisible: boolean;
  helpChatOpen: boolean;
  helpChatWidth: number;
  helpChatHeight: number;
  helpOnboardingSuppressed: boolean;
  sidebarCollapsed: boolean;
  windowMaximized: boolean;
  setHelpChatFabVisible: (visible: boolean) => void;
  setHelpChatOpen: (open: boolean) => void;
  setHelpChatSize: (size: { width?: number; height?: number }) => void;
  suppressHelpOnboarding: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setWindowMaximized: (maximized: boolean) => void;
}

export const createUiSlice: StateCreator<AppStore, [], [], UiSlice> = (set) => ({
  helpChatFabVisible: true,
  helpChatOpen: false,
  helpChatWidth: 0,
  helpChatHeight: 0,
  helpOnboardingSuppressed: false,
  sidebarCollapsed: false,
  windowMaximized: false,
  setHelpChatFabVisible: (helpChatFabVisible) => set({ helpChatFabVisible }),
  setHelpChatOpen: (helpChatOpen) => set({ helpChatOpen }),
  setHelpChatSize: (size) =>
    set((state) => ({
      helpChatWidth: size.width ?? state.helpChatWidth,
      helpChatHeight: size.height ?? state.helpChatHeight,
    })),
  suppressHelpOnboarding: () => set({ helpOnboardingSuppressed: true }),
  setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setWindowMaximized: (windowMaximized) => set({ windowMaximized }),
});
