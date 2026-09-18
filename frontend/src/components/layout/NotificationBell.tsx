import { useMemo, useState } from 'react';
import { Bell, Check, CircleAlert, CircleCheck, Info, Trash2, TriangleAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { formatRelative } from '@/lib/relativeTime';
import { cn } from '@/lib/utils';
import { useAppStore, type AppNotification, type NotificationVariant } from '@/store';

const VARIANT_ICON: Record<NotificationVariant, typeof Info> = {
  info: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  error: CircleAlert,
};

function NotificationList({ onClose }: { onClose?: () => void }) {
  const { t, i18n } = useTranslation();
  const notifications = useAppStore((state) => state.notifications);
  const markRead = useAppStore((state) => state.markRead);
  const markAllRead = useAppStore((state) => state.markAllRead);
  const clearNotifications = useAppStore((state) => state.clearNotifications);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <p className="text-sm font-semibold">{t('notifications.title')}</p>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={markAllRead}
            disabled={notifications.every((item) => item.read)}
          >
            {t('notifications.markAllRead')}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={t('notifications.clear')}
            onClick={() => {
              clearNotifications();
              onClose?.();
            }}
            disabled={notifications.length === 0}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      </div>
      <Separator />
      {notifications.length === 0 ? (
        <p className="px-3 py-8 text-center text-sm text-muted-foreground">
          {t('notifications.empty')}
        </p>
      ) : (
        <ScrollArea className="h-80">
          <ul className="flex flex-col p-1">
            {notifications.map((item) => (
              <NotificationRow
                key={item.id}
                item={item}
                locale={i18n.language}
                onRead={() => markRead(item.id)}
              />
            ))}
          </ul>
        </ScrollArea>
      )}
    </div>
  );
}

function NotificationRow({
  item,
  locale,
  onRead,
}: {
  item: AppNotification;
  locale: string;
  onRead: () => void;
}) {
  const { t } = useTranslation();
  const Icon = VARIANT_ICON[item.variant];
  return (
    <li
      className={cn(
        'flex gap-2 rounded-md px-2 py-2 text-sm',
        item.read ? 'opacity-70' : 'bg-accent/40',
      )}
    >
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="font-medium leading-5">{t(item.titleKey, item.values)}</p>
        {item.descriptionKey ? (
          <p className="text-xs text-muted-foreground">{t(item.descriptionKey, item.values)}</p>
        ) : null}
        <p className="mt-1 text-[11px] text-muted-foreground">
          {formatRelative(item.createdAt, locale)}
        </p>
      </div>
      {!item.read ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          aria-label={t('notifications.markRead')}
          onClick={onRead}
        >
          <Check className="size-3.5" />
        </Button>
      ) : null}
    </li>
  );
}

export function NotificationBell() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const unread = useAppStore(
    (state) => state.notifications.filter((item) => !item.read).length,
  );
  const label = useMemo(() => {
    const base = t('notifications.open');
    return unread > 0 ? `${base}. ${t('notifications.unreadCount', { count: unread })}` : base;
  }, [t, unread]);

  const trigger = (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="app-no-drag relative"
      aria-label={label}
      aria-expanded={open}
    >
      <Bell className="size-4" />
      {unread > 0 ? (
        <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground">
          {unread > 9 ? '9+' : unread}
        </span>
      ) : null}
    </Button>
  );

  if (isDesktop) {
    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>{trigger}</PopoverTrigger>
        <PopoverContent className="app-no-drag w-96 p-0">
          <NotificationList onClose={() => setOpen(false)} />
        </PopoverContent>
      </Popover>
    );
  }

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="app-no-drag relative"
        aria-label={label}
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <Bell className="size-4" />
        {unread > 0 ? (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground">
            {unread > 9 ? '9+' : unread}
          </span>
        ) : null}
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="bottom" closeLabel={t('nav.closeMenu')} className="h-[70vh]">
          <SheetHeader>
            <SheetTitle className="sr-only">{t('notifications.title')}</SheetTitle>
          </SheetHeader>
          <NotificationList onClose={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
    </>
  );
}
