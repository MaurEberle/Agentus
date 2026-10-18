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

export type ExportItem = {
  name: string;
  nodeCount: number;
  edgeCount: number;
};

export function ExportDialog({
  open,
  items,
  busy,
  onClose,
  onConfirm,
}: {
  open: boolean;
  items: ExportItem[];
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent closeLabel={t('networks.dialog.close')} className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('networks.transfer.exportTitle')}</DialogTitle>
          <DialogDescription>{t('networks.transfer.exportBody')}</DialogDescription>
        </DialogHeader>
        <ul className="max-h-60 space-y-2 overflow-auto">
          {items.map((item, index) => (
            <li key={`${item.name}-${index}`} className="rounded-md border px-3 py-2">
              <p className="text-sm font-medium">{item.name.trim() || t('network.untitled')}</p>
              <p className="text-xs text-muted-foreground">
                {t('networks.transfer.counts', { nodes: item.nodeCount, edges: item.edgeCount })}
              </p>
            </li>
          ))}
        </ul>
        {items.length > 1 ? <p className="text-xs text-muted-foreground">{t('networks.transfer.zipNote')}</p> : null}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            {t('networks.dialog.cancel')}
          </Button>
          <Button type="button" onClick={onConfirm} disabled={busy || items.length === 0} loading={busy}>
            {t('networks.transfer.download')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
