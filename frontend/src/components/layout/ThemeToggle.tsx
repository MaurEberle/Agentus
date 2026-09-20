import { Check, Monitor, Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const THEMES = [
  { value: 'light', icon: Sun, labelKey: 'shell.themeLight' },
  { value: 'dark', icon: Moon, labelKey: 'shell.themeDark' },
  { value: 'system', icon: Monitor, labelKey: 'shell.themeSystem' },
] as const;

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  const { theme, setTheme } = useTheme();
  const current = theme ?? 'system';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size={compact ? 'icon' : 'sm'} className="app-no-drag">
          <Sun className="size-4 dark:hidden" />
          <Moon className="hidden size-4 dark:block" />
          {!compact ? <span>{t('shell.theme')}</span> : null}
          <span className="sr-only">{t('shell.theme')}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="app-no-drag min-w-40">
        {THEMES.map((item) => {
          const Icon = item.icon;
          return (
            <DropdownMenuItem key={item.value} className="gap-2" onClick={() => setTheme(item.value)}>
              <Icon className="size-4 shrink-0" />
              <span className="flex-1">{t(item.labelKey)}</span>
              {current === item.value ? <Check className="size-4 shrink-0" /> : <span className="size-4 shrink-0" />}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
