import { useEffect, useState } from 'react';
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import type { NetworkListItem } from '@/modules/dashboard/model';

export function RenameDialog({
  item,
  busy,
  onClose,
  onSave,
}: {
  item: NetworkListItem | null;
  busy: boolean;
  onClose: () => void;
  onSave: (patch: { name: string; description: string }) => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  useEffect(() => {
    setName(item?.name ?? '');
    setDescription(item?.description ?? '');
  }, [item]);

  return (
    <Dialog open={item !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent closeLabel={t('networks.dialog.close')}>
        <DialogHeader>
          <DialogTitle>{t('networks.rename.title')}</DialogTitle>
          <DialogDescription>{t('networks.rename.body')}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="networks-rename">{t('networks.rename.name')}</Label>
            <Input id="networks-rename" value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="networks-rename-desc">{t('networks.rename.description')}</Label>
            <Textarea
              id="networks-rename-desc"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            {t('networks.dialog.cancel')}
          </Button>
          <Button type="button" disabled={busy || !name.trim()} onClick={() => onSave({ name: name.trim(), description })}>
            {t('networks.dialog.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
