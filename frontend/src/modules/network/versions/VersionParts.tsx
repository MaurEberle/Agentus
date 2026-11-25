import { useTranslation } from 'react-i18next';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import type { NetworkVersionItem } from '@/modules/network/versions/api';

/** "Editor", "Architekt", "wiederhergestellt aus Version 2" … */
export function VersionSource({ item }: { item: NetworkVersionItem }) {
  const { t } = useTranslation();
  if (item.source === 'restore') {
    return <>{item.restoredFrom ? t('network.versions.source.restoreFrom', { from: item.restoredFrom }) : t('network.versions.source.restore')}</>;
  }
  return <>{t(`network.versions.source.${item.source}`, { defaultValue: item.source })}</>;
}

/** Restoring replaces the editor's state; unsaved changes are asked about first. */
export function DiscardConfirm({ open, onCancel, onConfirm }: { open: boolean; onCancel: () => void; onConfirm: () => void }) {
  const { t } = useTranslation();
  return (
    <AlertDialog open={open} onOpenChange={(next) => (next ? undefined : onCancel())}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t('network.versions.dirtyTitle')}</AlertDialogTitle>
          <AlertDialogDescription>{t('network.versions.dirtyBody')}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <Button type="button" variant="outline" onClick={onCancel}>
            {t('network.dialog.cancel')}
          </Button>
          <Button type="button" onClick={onConfirm}>
            {t('network.versions.dirtyConfirm')}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
