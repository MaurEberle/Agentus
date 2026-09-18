import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Footer } from '@/components/layout/Footer';
import { Header } from '@/components/layout/Header';
import { Sidebar } from '@/components/layout/Sidebar';
import { Toaster } from '@/components/ui/sonner';
import { useHydrateSession } from '@/api/session';
import { notify } from '@/lib/notifications';

let welcomeSeeded = false;

export function AppShell() {
  const { t } = useTranslation();
  useHydrateSession();

  useEffect(() => {
    if (welcomeSeeded) return;
    welcomeSeeded = true;
    notify({
      titleKey: 'notify.welcome.title',
      descriptionKey: 'notify.welcome.desc',
      variant: 'info',
    });
  }, []);

  return (
    <div className="flex h-svh min-h-0 flex-col overflow-hidden bg-background">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2"
      >
        {t('app.skipToContent')}
      </a>
      <Header />
      <div className="flex min-h-0 min-w-0 flex-1">
        <Sidebar />
        <main id="main" className="min-h-0 min-w-0 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
      <Footer />
      <Toaster />
    </div>
  );
}
