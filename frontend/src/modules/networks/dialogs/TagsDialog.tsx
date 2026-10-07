import { useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { TagInput, type TagInputHandle } from '@/components/TagInput';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';

export function TagsDialog({
  open,
  count,
  busy,
  initialTags,
  suggestions,
  onClose,
  onSave,
}: {
  open: boolean;
  count: number;
  busy: boolean;
  initialTags: string[];
  suggestions?: string[];
  onClose: () => void;
  onSave: (tags: string[]) => void;
}) {
  const { t } = useTranslation();
  const inputRef = useRef<TagInputHandle>(null);
  const [tags, setTags] = useState<string[]>([]);

  useLayoutEffect(() => {
    if (open) setTags([...initialTags]);
    // Seed once when the dialog opens; keep edits until it closes.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initialTags is captured at open
  }, [open]);

  function reset() {
    setTags([...initialTags]);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          reset();
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
          <TagInput
            ref={inputRef}
            id="networks-tags"
            value={tags}
            onChange={setTags}
            placeholder={t('networks.tags.placeholder')}
            addLabel={t('networks.tags.add')}
            removeLabel={(tag) => t('networks.tags.remove', { tag })}
            suggestions={suggestions}
            describedBy="networks-tags-hint"
          />
          <p id="networks-tags-hint" className="text-xs text-muted-foreground">
            {t('networks.tags.hint')}
          </p>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            {t('networks.dialog.cancel')}
          </Button>
          <Button
            type="button"
            disabled={busy}
            onClick={() => {
              const next = inputRef.current?.commitDraft() ?? tags;
              onSave(next);
            }}
          >
            {t('networks.dialog.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
