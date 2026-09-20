import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ApiError } from '@/api/client';
import { notify } from '@/lib/notifications';
import {
  createCredential,
  deleteCredential,
  updateCredential,
  useCredentialsQuery,
} from '@/modules/settings/api';
import { CREDENTIAL_KINDS, type CredentialKind, type CredentialListItem } from '@/modules/settings/model';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';

type FormState = {
  id?: string;
  name: string;
  kind: CredentialKind;
  secret: string;
};

const emptyForm = (): FormState => ({ name: '', kind: 'token', secret: '' });

export function CredentialsSection() {
  const { t } = useTranslation();
  const { data } = useCredentialsQuery();
  const items = data?.items ?? [];
  const [form, setForm] = useState<FormState | null>(null);
  const [pendingDelete, setPendingDelete] = useState<CredentialListItem | null>(null);

  async function save() {
    if (!form || !form.name.trim()) return;
    try {
      if (form.id) {
        await updateCredential(form.id, {
          name: form.name.trim(),
          kind: form.kind,
          secret: form.secret || undefined,
        });
        notify({ titleKey: 'settings.notify.credentialUpdated', variant: 'success' });
      } else {
        if (!form.secret) return;
        await createCredential({ name: form.name.trim(), kind: form.kind, secret: form.secret });
        notify({ titleKey: 'settings.notify.credentialCreated', variant: 'success' });
      }
      setForm(null);
    } catch {
      notify({ titleKey: 'settings.notify.saveError', variant: 'error' });
    }
  }

  async function remove(item: CredentialListItem) {
    try {
      await deleteCredential(item.id);
      notify({ titleKey: 'settings.notify.credentialDeleted', variant: 'success' });
      setPendingDelete(null);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        notify({
          titleKey: 'settings.notify.credentialInUse',
          descriptionKey: 'settings.credentials.inUseBody',
          values: { name: item.name },
          variant: 'error',
        });
        return;
      }
      notify({ titleKey: 'settings.notify.saveError', variant: 'error' });
    }
  }

  return (
    <div className="max-w-3xl">
      <SectionHeader title={t('settings.nav.credentials')} description={t('settings.credentials.lead')} />
      <div className="mb-3 flex justify-end">
        <Button type="button" onClick={() => setForm(emptyForm())}>
          {t('settings.credentials.create')}
        </Button>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('settings.credentials.empty')}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('settings.credentials.name')}</TableHead>
              <TableHead>{t('settings.credentials.kind')}</TableHead>
              <TableHead>{t('settings.credentials.mask')}</TableHead>
              <TableHead className="text-right">{t('settings.common.actions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="font-medium">{item.name}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{t(`settings.credentials.kindName.${item.kind}`)}</Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">{item.mask}</TableCell>
                <TableCell className="space-x-2 text-right">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setForm({ id: item.id, name: item.name, kind: item.kind, secret: '' })
                    }
                  >
                    {t('settings.common.edit')}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setPendingDelete(item)}
                  >
                    {t('settings.common.delete')}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={form !== null} onOpenChange={(open) => !open && setForm(null)}>
        <DialogContent closeLabel={t('settings.common.close')}>
          <DialogHeader>
            <DialogTitle>
              {form?.id ? t('settings.credentials.editTitle') : t('settings.credentials.createTitle')}
            </DialogTitle>
            <DialogDescription>{t('settings.credentials.secretHint')}</DialogDescription>
          </DialogHeader>
          {form ? (
            <div className="grid gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="cred-name">{t('settings.credentials.name')}</Label>
                <Input
                  id="cred-name"
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                />
              </div>
              <div className="grid gap-1.5">
                <Label>{t('settings.credentials.kind')}</Label>
                <Select
                  value={form.kind}
                  onValueChange={(value) => setForm({ ...form, kind: value as CredentialKind })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CREDENTIAL_KINDS.filter((kind) => kind !== 'openai_compat').map((kind) => (
                      <SelectItem key={kind} value={kind}>
                        {t(`settings.credentials.kindName.${kind}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="cred-secret">{t('settings.credentials.secret')}</Label>
                <Input
                  id="cred-secret"
                  type="password"
                  autoComplete="new-password"
                  value={form.secret}
                  placeholder={form.id ? t('settings.credentials.secretUnchanged') : undefined}
                  onChange={(event) => setForm({ ...form, secret: event.target.value })}
                />
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setForm(null)}>
              {t('settings.common.cancel')}
            </Button>
            <Button type="button" onClick={() => void save()} disabled={!form?.name.trim() || (!form.id && !form.secret)}>
              {t('settings.common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={pendingDelete !== null} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <DialogContent closeLabel={t('settings.common.close')}>
          <DialogHeader>
            <DialogTitle>
              {pendingDelete?.inUse
                ? t('settings.credentials.inUseTitle')
                : t('settings.credentials.deleteTitle')}
            </DialogTitle>
            <DialogDescription>
              {pendingDelete?.inUse
                ? t('settings.credentials.inUseBody', { name: pendingDelete.name })
                : t('settings.credentials.deleteBody', { name: pendingDelete?.name ?? '' })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setPendingDelete(null)}>
              {t('settings.common.cancel')}
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={Boolean(pendingDelete?.inUse)}
              onClick={() => pendingDelete && void remove(pendingDelete)}
            >
              {t('settings.common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
