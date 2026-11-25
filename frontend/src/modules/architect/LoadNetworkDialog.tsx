import { useEffect, useMemo, useState } from 'react';
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
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { cn } from '@/lib/utils';
import type { LoadPurpose } from '@/modules/architect/api';
import { useEditorNetworksQuery } from '@/modules/network/api';

/** "Netz einlesen" (netz-architekt 13): pick a network and what it is for; reading in needs this click. */
export function LoadNetworkDialog({
  open,
  hasDraft,
  cloud,
  busy,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  hasDraft: boolean;
  cloud: boolean;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (networkId: string, purpose: LoadPurpose, name: string) => void;
}) {
  const { t } = useTranslation();
  const networks = useEditorNetworksQuery();
  const [query, setQuery] = useState('');
  const [picked, setPicked] = useState<string | null>(null);
  const [purpose, setPurpose] = useState<LoadPurpose>('change');

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setPicked(null);
    setPurpose('change');
  }, [open]);

  const items = useMemo(() => {
    const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return (networks.data?.items ?? []).filter((item) => {
      const text = `${item.name} ${item.description ?? ''} ${(item.tags ?? []).join(' ')}`.toLowerCase();
      return words.every((word) => text.includes(word));
    });
  }, [networks.data, query]);

  return (
    <Dialog open={open} onOpenChange={(next) => (busy ? undefined : onOpenChange(next))}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl" closeLabel={t('architect.closing.cancel')}>
        <DialogHeader>
          <DialogTitle>{t('architect.load.title')}</DialogTitle>
          <DialogDescription>{t('architect.load.lead')}</DialogDescription>
        </DialogHeader>
        <Input
          value={query}
          autoFocus
          placeholder={t('architect.load.search')}
          aria-label={t('architect.load.search')}
          onChange={(event) => setQuery(event.target.value)}
        />
        <ul className="grid max-h-64 gap-1 overflow-y-auto" role="listbox" aria-label={t('architect.load.title')}>
          {items.length === 0 ? (
            <li className="p-2 text-sm text-muted-foreground">{t('architect.load.empty')}</li>
          ) : (
            items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={picked === item.id}
                  onClick={() => setPicked(item.id)}
                  onDoubleClick={() => onConfirm(item.id, purpose, item.name)}
                  className={cn(
                    'w-full rounded-md border px-3 py-2 text-left text-sm hover:bg-muted',
                    picked === item.id && 'border-primary bg-primary/10',
                  )}
                >
                  <span className="block truncate font-medium">{item.name}</span>
                  {item.description ? (
                    <span className="block truncate text-xs text-muted-foreground">{item.description}</span>
                  ) : null}
                </button>
              </li>
            ))
          )}
        </ul>
        <fieldset className="grid gap-2 text-sm">
          <legend className="mb-1 font-medium">{t('architect.load.purposeLabel')}</legend>
          <RadioGroup value={purpose} onValueChange={(value) => setPurpose(value as LoadPurpose)}>
            {(['change', 'template'] as const).map((value) => (
              <label key={value} className="flex items-start gap-2">
                <RadioGroupItem value={value} id={`load-${value}`} className="mt-0.5" />
                <span>
                  <Label htmlFor={`load-${value}`}>{t(`architect.load.purpose.${value}`)}</Label>
                  <span className="block text-xs text-muted-foreground">{t(`architect.load.purposeHint.${value}`)}</span>
                </span>
              </label>
            ))}
          </RadioGroup>
        </fieldset>
        {hasDraft || cloud ? (
          <div className="grid gap-1 text-xs text-muted-foreground">
            {hasDraft ? <p>{t('architect.load.replaces')}</p> : null}
            {cloud ? <p>{t('architect.load.cloudNote')}</p> : null}
          </div>
        ) : null}
        <DialogFooter>
          <Button type="button" variant="outline" disabled={busy} onClick={() => onOpenChange(false)}>
            {t('architect.closing.cancel')}
          </Button>
          <Button type="button" disabled={!picked || busy} loading={busy} onClick={() => {
              const item = items.find((entry) => entry.id === picked);
              if (item) onConfirm(item.id, purpose, item.name);
            }}>
            {t('architect.load.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
