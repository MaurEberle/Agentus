import { useEffect } from 'react';
import { MessageCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { setOnboardingSeen } from '@/components/help-chat/api';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppStore } from '@/store';

export function HelpHintCard({
  onboardingSeen,
  loading,
}: {
  onboardingSeen?: boolean;
  loading: boolean;
}) {
  const { t } = useTranslation();
  const setHelpChatOpen = useAppStore((state) => state.setHelpChatOpen);
  const suppressHelpOnboarding = useAppStore((state) => state.suppressHelpOnboarding);

  useEffect(() => {
    if (onboardingSeen === false) suppressHelpOnboarding();
  }, [onboardingSeen, suppressHelpOnboarding]);

  if (loading) return <Skeleton className="h-28 w-full" />;
  if (onboardingSeen !== false) return null;

  function dismiss() {
    suppressHelpOnboarding();
    void setOnboardingSeen();
  }

  function openHelp() {
    suppressHelpOnboarding();
    setHelpChatOpen(true);
    void setOnboardingSeen();
  }

  return (
    <Alert className="pl-10">
      <MessageCircle className="size-4" />
      <AlertTitle>{t('dashboard.helpHint.title')}</AlertTitle>
      <AlertDescription>
        <p>{t('dashboard.helpHint.body')}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button type="button" size="sm" onClick={openHelp}>
            {t('dashboard.helpHint.open')}
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={dismiss}>
            {t('dashboard.helpHint.dismiss')}
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  );
}
