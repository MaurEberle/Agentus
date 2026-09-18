import type { LucideIcon } from 'lucide-react';
import type { ComponentType } from 'react';
import { Activity, GitBranch, History, LayoutDashboard, Library, Settings } from 'lucide-react';
import { DashboardPage } from '@/modules/dashboard';
import { HistoryPage } from '@/modules/history';
import { MonitoringPage } from '@/modules/monitoring';
import { NetworkPage } from '@/modules/network';
import { NetworksPage } from '@/modules/networks';
import { SettingsPage } from '@/modules/settings';

export interface AppModule {
  id: 'dashboard' | 'network' | 'networks' | 'monitoring' | 'history' | 'settings';
  titleKey: string;
  path: string;
  icon: LucideIcon;
  component: ComponentType;
}

export const NAV_MODULES: AppModule[] = [
  {
    id: 'dashboard',
    titleKey: 'nav.dashboard',
    path: '/dashboard',
    icon: LayoutDashboard,
    component: DashboardPage,
  },
  {
    id: 'network',
    titleKey: 'nav.network',
    path: '/network',
    icon: GitBranch,
    component: NetworkPage,
  },
  {
    id: 'networks',
    titleKey: 'nav.networks',
    path: '/networks',
    icon: Library,
    component: NetworksPage,
  },
  {
    id: 'monitoring',
    titleKey: 'nav.monitoring',
    path: '/monitoring',
    icon: Activity,
    component: MonitoringPage,
  },
  {
    id: 'history',
    titleKey: 'nav.history',
    path: '/history',
    icon: History,
    component: HistoryPage,
  },
];

export const SETTINGS_MODULE: AppModule = {
  id: 'settings',
  titleKey: 'nav.settings',
  path: '/settings',
  icon: Settings,
  component: SettingsPage,
};

export const ALL_MODULES: AppModule[] = [...NAV_MODULES, SETTINGS_MODULE];
