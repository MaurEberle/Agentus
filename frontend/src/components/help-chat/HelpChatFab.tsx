import type { Ref } from 'react';
import { useTranslation } from 'react-i18next';
import { BrandMark } from '@/components/BrandMark';
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
      variant="ghost"
      size="icon"
      className="app-no-drag relative size-[52px] rounded-full border border-border bg-white p-1 shadow-md hover:bg-white hover:shadow-lg"
      aria-label={open ? t('helpChat.fab.close') : t('helpChat.fab.open')}
      aria-expanded={open}
      onClick={onClick}
    >
      <BrandMark className="size-full" alt="" />
      {dot ? (
        <span className={cn('absolute right-1.5 top-1.5 size-2.5 rounded-full border border-background', dot)} />
      ) : null}
    </Button>
  );
}
