import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Menu } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '@/components/layout/LanguageSwitcher';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { NAV_MODULES, SETTINGS_MODULE } from '@/modules/registry';

export function MobileNav() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const items = [...NAV_MODULES, SETTINGS_MODULE];

  return (
    <div className="app-no-drag md:hidden">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-expanded={open}
        aria-label={open ? t('nav.closeMenu') : t('nav.openMenu')}
        onClick={() => setOpen(true)}
      >
        <Menu className="size-5" />
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" closeLabel={t('nav.closeMenu')} className="flex flex-col p-0">
          <SheetHeader className="p-4">
            <SheetTitle>{t('app.name')}</SheetTitle>
          </SheetHeader>
          <nav aria-label={t('nav.main')} className="flex flex-1 flex-col gap-1 px-2">
            {items.map((module) => {
              const Icon = module.icon;
              return (
                <NavLink
                  key={module.id}
                  to={module.path}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                      isActive && 'bg-accent text-accent-foreground',
                    )
                  }
                >
                  <Icon className="size-4" />
                  {t(module.titleKey)}
                </NavLink>
              );
            })}
          </nav>
          <Separator />
          <div className="flex items-center justify-between p-3">
            <ThemeToggle />
            <LanguageSwitcher />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
