import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { createNotificationsSlice } from '@/store/notifications';
import { createSessionSlice } from '@/store/session';
import type { AppStore } from '@/store/types';
import { createUiSlice } from '@/store/ui';

export const useAppStore = create<AppStore>()(
  persist(
    (...args) => ({
      ...createSessionSlice(...args),
      ...createNotificationsSlice(...args),
      ...createUiSlice(...args),
    }),
    {
      name: 'agentus-ui',
      partialize: (state) => ({
        helpChatFabVisible: state.helpChatFabVisible,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
    },
  ),
);

export type { AppStore } from '@/store/types';
export type { ServiceStatus } from '@/store/session';
export type { AppNotification, NotificationVariant } from '@/store/notifications';
