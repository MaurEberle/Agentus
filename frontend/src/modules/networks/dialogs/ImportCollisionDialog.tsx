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
import type { AgentNetworkDocument } from '@/modules/network/model/document';

export type CollisionRow = {
  fileName: string;
  document: AgentNetworkDocument;
};

type Draft = CollisionRow & { name: string; skip: boolean };

export function ImportCollisionDialog({
  rows,
  busy,
  onClose,
  onConfirm,
}: {
  rows: CollisionRow[] | null;
  busy: boolean;
  onClose: () => void;
  onConfirm: (accepted: Array<{ document: AgentNetworkDocument }>) => void;
}) {
  const { t } = useTranslation();
  const [drafts, setDrafts] = useState<Draft[]>([]);

  useEffect(() => {
    setDrafts(
      (rows ?? []).map((row) => ({
        ...row,
        name: row.document.name,
        skip: false,
      })),
    );
  }, [rows]);

  return (
    <Dialog open={rows !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent closeLabel={t('networks.dialog.close')} className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('networks.import.collisionTitle')}</DialogTitle>
          <DialogDescription>{t('networks.import.collisionBody')}</DialogDescription>
        </DialogHeader>
        <ul className="max-h-72 space-y-3 overflow-auto">
          {drafts.map((draft, index) => (
            <li key={`${draft.fileName}-${index}`} className="grid gap-1.5 rounded-md border p-2">
              <p className="text-xs text-muted-foreground">{draft.fileName}</p>
              <Label className="sr-only" htmlFor={`collision-${index}`}>
                {t('networks.rename.name')}
              </Label>
              <Input
                id={`collision-${index}`}
                value={draft.name}
                disabled={draft.skip}
                onChange={(event) =>
                  setDrafts((current) =>
                    current.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, name: event.target.value } : item,
                    ),
                  )
                }
              />
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() =>
                  setDrafts((current) =>
                    current.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, skip: !item.skip } : item,
                    ),
                  )
                }
              >
                {draft.skip ? t('networks.import.include') : t('networks.import.skip')}
              </Button>
            </li>
          ))}
        </ul>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            {t('networks.dialog.cancel')}
          </Button>
          <Button
            type="button"
            disabled={busy}
            onClick={() => {
              const accepted = drafts
                .filter((draft) => !draft.skip && draft.name.trim())
                .map((draft) => ({ document: { ...draft.document, name: draft.name.trim() } }));
              onConfirm(accepted);
            }}
          >
            {t('networks.import.continue')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
