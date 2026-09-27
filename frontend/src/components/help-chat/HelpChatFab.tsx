import { useState, type Ref } from 'react';
import { useTranslation } from 'react-i18next';
import { BrandMark } from '@/components/BrandMark';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { HelpChatUiStatus } from '@/components/help-chat/model';

export function HelpChatFab({
  open,
  status,
  size,
  onClick,
  buttonRef,
}: {
  open: boolean;
  status: HelpChatUiStatus;
  size: number;
  onClick: () => void;
  buttonRef: Ref<HTMLButtonElement>;
}) {
  const { t } = useTranslation();
  const [hovered, setHovered] = useState(false);
  const dot =
    status === 'error' ? 'bg-destructive' : status === 'unconfigured' ? 'bg-warning' : null;

  return (
    <Button
      ref={buttonRef}
      type="button"
      variant="ghost"
      size="icon"
      style={{ width: size, height: size, minWidth: size, minHeight: size }}
      className="app-no-drag relative rounded-full border border-border bg-card p-1 shadow-md transition-[transform,box-shadow,background-color] hover:bg-accent hover:shadow-lg motion-safe:hover:scale-105"
      aria-label={open ? t('helpChat.fab.close') : t('helpChat.fab.open')}
      aria-expanded={open}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
    >
      <BrandMark chill={hovered} className="size-full" alt="" />
      {dot ? (
        <span className={cn('absolute right-2 top-2 size-2.5 rounded-full border border-background', dot)} />
      ) : null}
    </Button>
  );
}
