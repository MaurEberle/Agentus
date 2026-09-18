import i18n from '@/i18n';
import { toast } from 'sonner';
import { useAppStore, type NotificationVariant } from '@/store';

export interface NotifyOptions {
  titleKey: string;
  descriptionKey?: string;
  variant?: NotificationVariant;
  persist?: boolean;
  values?: Record<string, string>;
}

function showToast(
  variant: NotificationVariant,
  title: string,
  description?: string,
) {
  const options = { description };
  switch (variant) {
    case 'success':
      toast.success(title, options);
      break;
    case 'warning':
      toast.warning(title, options);
      break;
    case 'error':
      toast.error(title, options);
      break;
    default:
      toast.info(title, options);
  }
}

export function notify(options: NotifyOptions) {
  const variant = options.variant ?? 'info';
  const title = i18n.t(options.titleKey, options.values);
  const description = options.descriptionKey
    ? i18n.t(options.descriptionKey, options.values)
    : undefined;

  showToast(variant, title, description);

  if (options.persist !== false) {
    useAppStore.getState().addNotification({
      titleKey: options.titleKey,
      descriptionKey: options.descriptionKey,
      values: options.values,
      variant,
    });
  }
}
