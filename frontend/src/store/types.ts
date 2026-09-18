import type { NotificationsSlice } from '@/store/notifications';
import type { SessionSlice } from '@/store/session';
import type { UiSlice } from '@/store/ui';

export type AppStore = SessionSlice & NotificationsSlice & UiSlice;
