import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { HelpChatFab } from '@/components/help-chat/HelpChatFab';
import { HelpChatOnboarding } from '@/components/help-chat/HelpChatOnboarding';
import { HelpChatPanel } from '@/components/help-chat/HelpChatPanel';
import { useHelpChatStatusQuery } from '@/components/help-chat/api';
import { deriveHelpStatus, helpChatAnchor } from '@/components/help-chat/model';
import { useHelpChatWidget } from '@/components/help-chat/store';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { useViewportSize } from '@/hooks/useViewportSize';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';

export function HelpChatHost() {
  const { t } = useTranslation();
  const visible = useAppStore((state) => state.helpChatFabVisible);
  const open = useAppStore((state) => state.helpChatOpen);
  const setHelpChatOpen = useAppStore((state) => state.setHelpChatOpen);
  const suppressed = useAppStore((state) => state.helpOnboardingSuppressed);
  const { data: status } = useHelpChatStatusQuery();
  const generating = useHelpChatWidget((state) => state.generating);
  const errorKey = useHelpChatWidget((state) => state.errorKey);
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');
  const viewport = useViewportSize();
  const { fab, inset, bottom, right } = helpChatAnchor(viewport);
  const fabRef = useRef<HTMLButtonElement>(null);
  const [onboarding, setOnboarding] = useState(false);

  useEffect(() => {
    if (open && status && !status.onboardingSeen && !suppressed) {
      setOnboarding(true);
    }
  }, [open, status, suppressed]);

  if (!visible) return null;

  const uiStatus = deriveHelpStatus({
    configured: Boolean(status?.configured),
    generating,
    error: Boolean(errorKey),
    degraded: status?.degraded,
  });

  function close() {
    setHelpChatOpen(false);
    window.setTimeout(() => fabRef.current?.focus(), 0);
  }

  function toggle() {
    setHelpChatOpen(!open);
  }

  return (
    <>
      <div
        className="pointer-events-none fixed z-30"
        style={{ bottom: inset, right: inset }}
      >
        <div className="pointer-events-auto">
          <HelpChatFab open={open} status={uiStatus} size={fab} onClick={toggle} buttonRef={fabRef} />
        </div>
      </div>
      {isDesktop && open ? (
        <div
          className={cn(
            'fixed z-40',
            reducedMotion ? 'opacity-100' : 'animate-in fade-in slide-in-from-bottom-2 duration-200',
          )}
          style={{ bottom, right }}
        >
          <HelpChatPanel compact={false} status={status} onClose={close} />
        </div>
      ) : null}
      {!isDesktop ? (
        <Sheet open={open} onOpenChange={(next) => (next ? setHelpChatOpen(true) : close())}>
          <SheetContent side="bottom" closeLabel={t('helpChat.action.close')} className="h-[80vh] p-0">
            <SheetHeader className="sr-only">
              <SheetTitle>{t('helpChat.title')}</SheetTitle>
            </SheetHeader>
            <HelpChatPanel compact status={status} onClose={close} />
          </SheetContent>
        </Sheet>
      ) : null}
      <HelpChatOnboarding open={onboarding} onClose={() => setOnboarding(false)} />
    </>
  );
}
