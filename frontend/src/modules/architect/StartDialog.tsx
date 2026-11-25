import { useTranslation } from 'react-i18next';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { formatBytes } from '@/lib/format';
import type { StartRefused } from '@/modules/architect/api';

/**
 * Why a start was refused, and the conscious exceptions (E-7, E-20): start slowly with layers
 * in system memory, and start although a network is running.
 */
export function StartDialog({
  refusal,
  onCancel,
  onConfirm,
}: {
  refusal: StartRefused | null;
  onCancel: () => void;
  onConfirm: (options: { forceSlow?: boolean; confirmRunning?: boolean }) => void;
}) {
  const { t, i18n } = useTranslation();
  if (!refusal) return null;
  const gpu = refusal.gpu;
  const sizes = gpu
    ? {
        need: formatBytes(gpu.needBytes, i18n.language),
        free: formatBytes(gpu.freeVramBytes, i18n.language),
        ram: formatBytes(gpu.freeRamBytes, i18n.language),
      }
    : null;
  const key = refusal.messageKey;
  const slow = key === 'architect.gpu.short';
  const running = key === 'architect.networkRunning' || (slow && Boolean(gpu?.networkRunning));
  const blocked = key === 'architect.gpu.tooLarge' || key === 'architect.model.blocked' || !(slow || running);
  return (
    <AlertDialog open onOpenChange={(open) => (open ? undefined : onCancel())}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t(slow ? 'architect.start.slowTitle' : running ? 'architect.start.runningTitle' : 'architect.start.blockedTitle')}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="grid gap-2 text-sm">
              {slow && sizes ? <p>{t('architect.start.slowBody', sizes)}</p> : null}
              {key === 'architect.gpu.tooLarge' && sizes ? <p>{t('architect.start.tooLargeBody', sizes)}</p> : null}
              {running ? <p className="font-medium text-destructive">{t('architect.start.runningBody')}</p> : null}
              {key === 'architect.model.blocked'
                ? (refusal.model?.reasons ?? []).map((reason) => <p key={reason}>{t(reason)}</p>)
                : null}
              {blocked && key !== 'architect.model.blocked' && key !== 'architect.gpu.tooLarge' ? <p>{t(key, { defaultValue: t('architect.failed') })}</p> : null}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t(blocked ? 'architect.start.close' : 'architect.start.cancel')}</AlertDialogCancel>
          {!blocked ? (
            <AlertDialogAction
              className={running ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90' : undefined}
              onClick={() => onConfirm({ forceSlow: slow || undefined, confirmRunning: running || undefined })}
            >
              {t(slow ? 'architect.start.slowConfirm' : 'architect.start.runningConfirm')}
            </AlertDialogAction>
          ) : null}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
