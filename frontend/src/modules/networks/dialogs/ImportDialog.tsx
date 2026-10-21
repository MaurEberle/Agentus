import { useEffect, useMemo, useRef, useState } from 'react';
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
import { isImportFail, parseImportJson } from '@/modules/networks/model/importDoc';

type Draft =
  | { ok: false; fileName: string; reason: 'unreadable' | 'schema' }
  | {
      ok: true;
      fileName: string;
      document: AgentNetworkDocument;
      name: string;
      skip: boolean;
      stripped: boolean;
    };

export function ImportDialog({
  open,
  multiple,
  existingNames,
  busy,
  onClose,
  onImport,
}: {
  open: boolean;
  multiple: boolean;
  existingNames: string[];
  busy: boolean;
  onClose: () => void;
  onImport: (documents: AgentNetworkDocument[]) => void;
}) {
  const { t } = useTranslation();
  const fileRef = useRef<HTMLInputElement>(null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const existing = useMemo(
    () => new Set(existingNames.map((name) => name.trim().toLowerCase()).filter(Boolean)),
    [existingNames],
  );

  useEffect(() => {
    if (!open) setDrafts([]);
  }, [open]);

  function clashes(name: string, index: number): boolean {
    const key = name.trim().toLowerCase();
    if (!key) return false;
    if (existing.has(key)) return true;
    return drafts.some((other, otherIndex) => {
      if (otherIndex === index || !other.ok || other.skip) return false;
      return other.name.trim().toLowerCase() === key;
    });
  }

  function readyDocuments(): AgentNetworkDocument[] {
    const documents: AgentNetworkDocument[] = [];
    drafts.forEach((draft, index) => {
      if (!draft.ok || draft.skip) return;
      const name = draft.name.trim();
      if (!name || clashes(name, index)) return;
      documents.push({ ...draft.document, name });
    });
    return documents;
  }

  async function onFiles(list: FileList | null) {
    if (!list?.length) return;
    const next: Draft[] = [];
    for (const file of Array.from(list)) {
      try {
        const parsed = parseImportJson(file.name, JSON.parse(await file.text()) as unknown);
        if (isImportFail(parsed)) {
          next.push({
            ok: false,
            fileName: file.name,
            reason: parsed.errorKey.endsWith('schema') ? 'schema' : 'unreadable',
          });
          continue;
        }
        next.push({
          ok: true,
          fileName: file.name,
          document: parsed.document,
          name: parsed.document.name,
          skip: false,
          stripped: parsed.strippedSecrets,
        });
      } catch {
        next.push({ ok: false, fileName: file.name, reason: 'unreadable' });
      }
    }
    setDrafts(next);
    if (fileRef.current) fileRef.current.value = '';
  }

  const ready = readyDocuments();
  const blocked = drafts.some((draft, index) => {
    if (!draft.ok || draft.skip) return false;
    return !draft.name.trim() || clashes(draft.name, index);
  });
  const stripped = drafts.some((draft) => draft.ok && draft.stripped);

  return (
    <Dialog open={open} onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent closeLabel={t('networks.dialog.close')} className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('networks.transfer.importTitle')}</DialogTitle>
          <DialogDescription>{t('networks.transfer.importBody')}</DialogDescription>
        </DialogHeader>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          multiple={multiple}
          className="hidden"
          onChange={(event) => void onFiles(event.target.files)}
        />
        <Button type="button" variant="outline" onClick={() => fileRef.current?.click()} disabled={busy}>
          {t('networks.transfer.pick')}
        </Button>
        {drafts.length === 0 ? <p className="text-sm text-muted-foreground">{t('networks.transfer.empty')}</p> : null}
        {stripped ? <p className="text-xs text-muted-foreground">{t('networks.transfer.secrets')}</p> : null}
        <ul className="max-h-72 space-y-3 overflow-auto">
          {drafts.map((draft, index) => (
            <li key={`${draft.fileName}-${index}`} className="grid gap-1.5 rounded-md border p-2">
              <p className="text-xs text-muted-foreground">{draft.fileName}</p>
              {draft.ok ? (
                <>
                  <Label className="sr-only" htmlFor={`import-name-${index}`}>
                    {t('networks.transfer.name')}
                  </Label>
                  <Input
                    id={`import-name-${index}`}
                    value={draft.name}
                    disabled={draft.skip || busy}
                    onChange={(event) =>
                      setDrafts((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index && item.ok ? { ...item, name: event.target.value } : item,
                        ),
                      )
                    }
                  />
                  {!draft.name.trim() ? (
                    <p className="text-xs text-destructive">{t('networks.transfer.nameRequired')}</p>
                  ) : null}
                  {draft.name.trim() && clashes(draft.name, index) ? (
                    <p className="text-xs text-destructive">{t('networks.transfer.collision')}</p>
                  ) : null}
                  <p className="text-xs text-muted-foreground">
                    {t('networks.transfer.counts', {
                      nodes: draft.document.nodes.length,
                      edges: draft.document.edges.length,
                    })}
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    onClick={() =>
                      setDrafts((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index && item.ok ? { ...item, skip: !item.skip } : item,
                        ),
                      )
                    }
                  >
                    {draft.skip ? t('networks.transfer.include') : t('networks.transfer.skip')}
                  </Button>
                </>
              ) : (
                <p className="text-xs text-destructive">
                  {t(draft.reason === 'schema' ? 'networks.transfer.fileSchema' : 'networks.transfer.fileUnreadable')}
                </p>
              )}
            </li>
          ))}
        </ul>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            {t('networks.dialog.cancel')}
          </Button>
          <Button
            type="button"
            disabled={busy || blocked || ready.length === 0}
            loading={busy}
            onClick={() => onImport(ready)}
          >
            {t('networks.transfer.confirmImport')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
