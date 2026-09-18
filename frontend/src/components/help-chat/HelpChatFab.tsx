import type { Ref } from 'react';
import { MessageCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { HelpChatUiStatus } from '@/components/help-chat/model';

export function HelpChatFab({
  open,
  status,
  onClick,
  buttonRef,
}: {
  open: boolean;
  status: HelpChatUiStatus;
  onClick: () => void;
  buttonRef: Ref<HTMLButtonElement>;
}) {
  const { t } = useTranslation();
  const dot =
    status === 'error' ? 'bg-destructive' : status === 'unconfigured' ? 'bg-warning' : null;

  return (
    <Button
      ref={buttonRef}
      type="button"
      size="icon"
      className="app-no-drag relative size-12 rounded-full shadow-lg"
      aria-label={open ? t('helpChat.fab.close') : t('helpChat.fab.open')}
      aria-expanded={open}
      onClick={onClick}
    >
      <MessageCircle className="size-5" />
      {dot ? (
        <span className={cn('absolute right-1.5 top-1.5 size-2.5 rounded-full border border-background', dot)} />
      ) : null}
    </Button>
  );
}
