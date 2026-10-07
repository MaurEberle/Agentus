import { useEffect, useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FolderPickerHost } from '@/components/FolderPickerHost';
import { HelpChatHost } from '@/components/help-chat/HelpChatHost';
import { BootScreen } from '@/components/layout/BootScreen';
import { Footer } from '@/components/layout/Footer';
import { Header } from '@/components/layout/Header';
import { Sidebar } from '@/components/layout/Sidebar';
import { Toaster } from '@/components/ui/sonner';
import { useHydrateSession, useSessionQuery } from '@/api/session';
import { notify } from '@/lib/notifications';
import { registerWaitAskOpen } from '@/lib/waitAsk';
import { useLiveRunEvents } from '@/modules/monitoring/live/adapter';
import { useMonitoringStore } from '@/modules/monitoring/store';

let welcomeSeeded = false;

function hideHtmlBootSplash() {
  document.getElementById('boot-splash')?.remove();
}

function WaitAskHost() {
  const navigate = useNavigate();
  useLiveRunEvents();
  useEffect(() => {
    return registerWaitAskOpen(() => {
      useMonitoringStore.getState().setPendingChatFocus(true);
      useMonitoringStore.getState().setTab('chat');
      navigate('/monitoring');
    });
  }, [navigate]);
  return null;
}

export function AppShell() {
  const { t } = useTranslation();
  const { isPending } = useSessionQuery();
  const [bootTimedOut, setBootTimedOut] = useState(false);
  useHydrateSession();

  useEffect(() => {
    hideHtmlBootSplash();
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setBootTimedOut(true), 20000);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (isPending || welcomeSeeded) return;
    welcomeSeeded = true;
    notify({
      titleKey: 'notify.welcome.title',
      descriptionKey: 'notify.welcome.desc',
      variant: 'info',
    });
  }, [isPending]);

  if (isPending && !bootTimedOut) {
    return <BootScreen />;
  }

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
      <FolderPickerHost />
      <HelpChatHost />
      <WaitAskHost />
    </div>
  );
}
