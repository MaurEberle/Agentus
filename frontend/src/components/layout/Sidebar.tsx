import { NavLink } from 'react-router-dom';
import { ChevronsLeft, ChevronsRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { NAV_MODULES } from '@/modules/registry';
import { useAppStore } from '@/store';

export function Sidebar() {
  const { t } = useTranslation();
  const collapsed = useAppStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);

  return (
    <aside
      className={cn(
        'hidden h-full shrink-0 flex-col border-r bg-card/60 md:flex',
        collapsed ? 'w-14' : 'w-56',
      )}
    >
      <nav aria-label={t('nav.main')} className="flex flex-1 flex-col gap-1 p-2">
        {NAV_MODULES.map((module) => {
          const Icon = module.icon;
          return (
            <NavLink
              key={module.id}
              to={module.path}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-2.5 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                  isActive && 'bg-accent text-accent-foreground',
                  collapsed && 'justify-center px-0',
                )
              }
            >
              <Icon className="size-4 shrink-0" />
              {!collapsed ? <span className="truncate">{t(module.titleKey)}</span> : null}
              {collapsed ? <span className="sr-only">{t(module.titleKey)}</span> : null}
            </NavLink>
          );
        })}
      </nav>
      <div className="p-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="w-full justify-center"
          onClick={toggleSidebar}
          aria-label={t(collapsed ? 'nav.expand' : 'nav.collapse')}
        >
          {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
        </Button>
      </div>
    </aside>
  );
}
