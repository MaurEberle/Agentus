import type { StateCreator } from 'zustand';
import type { AppStore } from '@/store/types';

export type NotificationVariant = 'success' | 'info' | 'warning' | 'error';

export interface AppNotification {
  id: string;
  titleKey: string;
  descriptionKey?: string;
  values?: Record<string, string>;
  variant: NotificationVariant;
  createdAt: number;
  read: boolean;
}

const MAX_NOTIFICATIONS = 50;

export interface NotificationsSlice {
  notifications: AppNotification[];
  addNotification: (
    input: Omit<AppNotification, 'id' | 'createdAt' | 'read'> & { id?: string },
  ) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  clearNotifications: () => void;
}

export const createNotificationsSlice: StateCreator<AppStore, [], [], NotificationsSlice> = (
  set,
) => ({
  notifications: [],
  addNotification: (input) =>
    set((state) => {
      const next: AppNotification = {
        id: input.id ?? crypto.randomUUID(),
        titleKey: input.titleKey,
        descriptionKey: input.descriptionKey,
        values: input.values,
        variant: input.variant,
        createdAt: Date.now(),
        read: false,
      };
      return {
        notifications: [next, ...state.notifications].slice(0, MAX_NOTIFICATIONS),
      };
    }),
  markRead: (id) =>
    set((state) => ({
      notifications: state.notifications.map((item) =>
        item.id === id ? { ...item, read: true } : item,
      ),
    })),
  markAllRead: () =>
    set((state) => ({
      notifications: state.notifications.map((item) => ({ ...item, read: true })),
    })),
  clearNotifications: () => set({ notifications: [] }),
});
