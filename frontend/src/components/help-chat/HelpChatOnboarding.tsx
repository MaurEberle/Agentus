import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { setOnboardingSeen } from '@/components/help-chat/api';
import { useAppStore } from '@/store';

export function HelpChatOnboarding({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const suppressHelpOnboarding = useAppStore((state) => state.suppressHelpOnboarding);

  async function finish(goToSettings: boolean) {
    await setOnboardingSeen();
    suppressHelpOnboarding();
    onClose();
    if (goToSettings) {
      navigate({ pathname: '/settings', hash: 'help-chat' });
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && void finish(false)}>
      <DialogContent closeLabel={t('helpChat.action.close')} className="app-no-drag">
        <DialogHeader>
          <DialogTitle>{t('helpChat.onboarding.title')}</DialogTitle>
          <DialogDescription>{t('helpChat.onboarding.body')}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => void finish(false)}>
            {t('helpChat.onboarding.later')}
          </Button>
          <Button type="button" onClick={() => void finish(true)}>
            {t('helpChat.onboarding.configure')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
