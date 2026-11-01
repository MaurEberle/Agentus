import type { LucideIcon } from 'lucide-react';
import type { ComponentType } from 'react';
import { Activity, Cpu, Download, GitBranch, History, LayoutDashboard, Library, ScrollText, Settings } from 'lucide-react';
import { DashboardPage } from '@/modules/dashboard';
import { HistoryPage } from '@/modules/history';
import { MonitoringPage } from '@/modules/monitoring';
import { NetworkPage } from '@/modules/network';
import { NetworksPage } from '@/modules/networks';
import { DownloadsPage } from '@/modules/downloads';
import { ModelsPage } from '@/modules/models';
import { PromptsPage } from '@/modules/prompts';
import { SettingsPage } from '@/modules/settings';

export interface AppModule {
  id: 'dashboard' | 'network' | 'networks' | 'prompts' | 'models' | 'monitoring' | 'history' | 'downloads' | 'settings';
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
    id: 'prompts',
    titleKey: 'nav.prompts',
    path: '/prompts',
    icon: ScrollText,
    component: PromptsPage,
  },
  {
    id: 'models',
    titleKey: 'nav.models',
    path: '/models',
    icon: Cpu,
    component: ModelsPage,
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

export const DOWNLOADS_MODULE: AppModule = {
  id: 'downloads',
  titleKey: 'models.downloads.title',
  path: '/downloads',
  icon: Download,
  component: DownloadsPage,
};

export const SETTINGS_MODULE: AppModule = {
  id: 'settings',
  titleKey: 'nav.settings',
  path: '/settings',
  icon: Settings,
  component: SettingsPage,
};

export const ALL_MODULES: AppModule[] = [...NAV_MODULES, DOWNLOADS_MODULE, SETTINGS_MODULE];
