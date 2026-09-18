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
import type { NetworkListItem } from '@/modules/dashboard/model';

export function DeleteDialog({
  items,
  busy,
  onClose,
  onConfirm,
}: {
  items: NetworkListItem[] | null;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const { t } = useTranslation();
  const list = items ?? [];
  const running = list.filter((item) => item.isRunning);
  const deletable = list.filter((item) => !item.isRunning);
  const active = deletable.filter((item) => item.isActive);

  return (
    <Dialog open={items !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent closeLabel={t('networks.dialog.close')}>
        <DialogHeader>
          <DialogTitle>{t('networks.delete.title')}</DialogTitle>
          <DialogDescription>{t('networks.delete.body')}</DialogDescription>
        </DialogHeader>
        {deletable.length > 0 ? (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {deletable.map((item) => (
              <li key={item.id}>{item.name}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{t('networks.delete.none')}</p>
        )}
        {running.length > 0 ? (
          <p className="text-sm text-muted-foreground">
            {t('networks.delete.runningSkipped', { names: running.map((item) => item.name).join(', ') })}
          </p>
        ) : null}
        {active.length > 0 ? <p className="text-sm text-destructive">{t('networks.delete.activeWarning')}</p> : null}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            {t('networks.dialog.cancel')}
          </Button>
          <Button type="button" variant="destructive" disabled={busy || deletable.length === 0} onClick={onConfirm}>
            {t('networks.ribbon.delete')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
