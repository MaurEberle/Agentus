import { Link } from 'react-router-dom';
import { Play, Settings, Square } from 'lucide-react';
import { BrandMark } from '@/components/BrandMark';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '@/components/layout/LanguageSwitcher';
import { MobileNav } from '@/components/layout/MobileNav';
import { NotificationBell } from '@/components/layout/NotificationBell';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { WindowControls } from '@/components/layout/WindowControls';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { selectActiveNetwork, startActiveRun, stopActiveRun, useNetworkOptions } from '@/api/session';
import { useAppStore } from '@/store';

export function Header() {
  const { t } = useTranslation();
  const activeNetworkId = useAppStore((state) => state.activeNetworkId);
  const serviceStatus = useAppStore((state) => state.serviceStatus);
  const { data } = useNetworkOptions();
  const networks = data?.items ?? [];

  const startDisabled =
    !activeNetworkId ||
    serviceStatus === 'starting' ||
    serviceStatus === 'running' ||
    serviceStatus === 'stopping';
  const stopDisabled = serviceStatus === 'stopped' || serviceStatus === 'disconnected';

  return (
    <header className="relative flex h-12 shrink-0 items-center gap-2 border-b bg-card/80 px-2 backdrop-blur md:px-3">
      <div className="app-drag absolute inset-0" aria-hidden="true" />
      <div className="relative z-10">
        <MobileNav />
      </div>
      <Link
        to="/dashboard"
        className="app-no-drag relative z-10 flex items-center gap-2 rounded-md px-1.5 py-1 text-sm font-semibold tracking-tight hover:bg-accent"
      >
        <BrandMark className="size-6" alt={t('app.name')} />
        <span className="hidden sm:inline">{t('app.name')}</span>
      </Link>
      <div className="app-drag relative z-10 min-w-2 flex-1 self-stretch" />
      <div className="app-no-drag relative z-10 hidden items-center gap-1 md:flex">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/settings#appearance">
            <Settings className="size-4" />
            {t('shell.settings')}
          </Link>
        </Button>
      </div>
      <div className="app-no-drag relative z-10 flex items-center gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              size="sm"
              disabled={startDisabled}
              onClick={() => void startActiveRun()}
            >
              <Play className="size-4" />
              <span className="hidden md:inline">{t('shell.start')}</span>
              <span className="sr-only md:hidden">{t('shell.start')}</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t('shell.start')}</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={stopDisabled}
              onClick={() => void stopActiveRun()}
            >
              <Square className="size-4" />
              <span className="hidden md:inline">{t('shell.stop')}</span>
              <span className="sr-only md:hidden">{t('shell.stop')}</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t('shell.stop')}</TooltipContent>
        </Tooltip>
        <Select
          value={activeNetworkId ?? 'none'}
          onValueChange={(value) => void selectActiveNetwork(value === 'none' ? null : value)}
        >
          <SelectTrigger
            className="h-8 w-[9.5rem] sm:w-48"
            aria-label={t('shell.quickSelect')}
          >
            <SelectValue placeholder={t('shell.quickSelectPlaceholder')} />
          </SelectTrigger>
          <SelectContent className="app-no-drag">
            <SelectItem value="none">{t('shell.noNetwork')}</SelectItem>
            {networks.map((network) => (
              <SelectItem key={network.id} value={network.id}>
                {network.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="app-no-drag relative z-10 flex items-center gap-2">
        <NotificationBell />
        <div className="hidden items-center gap-2 md:flex">
          <ThemeToggle compact />
          <LanguageSwitcher compact />
        </div>
      </div>
      <div className="relative z-10">
        <WindowControls />
      </div>
    </header>
  );
}
