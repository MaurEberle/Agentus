import { useState } from 'react';
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

export function TagsDialog({
  open,
  count,
  busy,
  onClose,
  onSave,
}: {
  open: boolean;
  count: number;
  busy: boolean;
  onClose: () => void;
  onSave: (tags: string[]) => void;
}) {
  const { t } = useTranslation();
  const [value, setValue] = useState('');

  function parse(raw: string): string[] {
    return [...new Set(raw.split(/[,;\s]+/).map((item) => item.trim()).filter(Boolean))];
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setValue('');
          onClose();
        }
      }}
    >
      <DialogContent closeLabel={t('networks.dialog.close')}>
        <DialogHeader>
          <DialogTitle>{t('networks.tags.title')}</DialogTitle>
          <DialogDescription>{t('networks.tags.body', { count })}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-1.5">
          <Label htmlFor="networks-tags">{t('networks.tags.label')}</Label>
          <Input
            id="networks-tags"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder={t('networks.tags.placeholder')}
          />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            {t('networks.dialog.cancel')}
          </Button>
          <Button
            type="button"
            disabled={busy || parse(value).length === 0}
            onClick={() => {
              const tags = parse(value);
              if (tags.length === 0) return;
              onSave(tags);
              setValue('');
            }}
          >
            {t('networks.tags.add')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
