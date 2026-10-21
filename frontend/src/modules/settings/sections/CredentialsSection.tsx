import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { TFunction } from 'i18next';
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
import {
  CREDENTIAL_GROUPS,
  CREDENTIAL_KINDS_BY_GROUP,
  SELECTABLE_MCP_CREDENTIAL_KINDS,
  credentialGroup,
  type CredentialGroup,
  type CredentialKind,
  type CredentialListItem,
} from '@/modules/settings/model';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';

function PairEditor({
  rows,
  nameLabel,
  valueLabel,
  addLabel,
  onChange,
}: {
  rows: SecretPair[];
  nameLabel: string;
  valueLabel: string;
  addLabel: string;
  onChange: (rows: SecretPair[]) => void;
}) {
  return (
    <div className="grid gap-1.5">
      {rows.map((row, index) => (
        <div key={index} className="flex gap-2">
          <Input
            value={row.name}
            placeholder={nameLabel}
            spellCheck={false}
            onChange={(event) => {
              const next = rows.slice();
              next[index] = { ...row, name: event.target.value };
              onChange(next);
            }}
          />
          <Input
            type="password"
            autoComplete="new-password"
            value={row.value}
            placeholder={valueLabel}
            onChange={(event) => {
              const next = rows.slice();
              next[index] = { ...row, value: event.target.value };
              onChange(next);
            }}
          />
        </div>
      ))}
      {rows.length < 8 ? (
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => onChange([...rows, { name: '', value: '' }])}
        >
          {addLabel}
        </Button>
      ) : null}
    </div>
  );
}

function usageLabelText(label: string, t: TFunction): string {
  if (label === 'helpChat.llm') return t('settings.credentials.usedBy.helpChatLlm');
  if (label === 'helpChat.embedding') return t('settings.credentials.usedBy.helpChatEmbed');
  if (label === 'helpChat.webSearch') return t('settings.credentials.usedBy.helpChatSearch');
  if (label.startsWith('mcp:')) {
    const id = label.slice(4);
    const name = t(`mcp.recipe.${id}`, { defaultValue: id });
    return t('settings.credentials.usedBy.mcp', { name });
  }
  if (label.startsWith('network:')) {
    const parts = label.split(':');
    const name = parts.slice(2).join(':') || parts[1] || label;
    return t('settings.credentials.usedBy.network', { name });
  }
  return label;
}

type SecretPair = { name: string; value: string };

type FormState = {
  id?: string;
  name: string;
  kind: CredentialKind;
  secret: string;
  token: string;
  headers: SecretPair[];
  env: SecretPair[];
};

function canSave(form: FormState | null): boolean {
  if (!form?.name.trim()) return false;
  if (form.id) return true;
  if (form.kind === 'custom') return encodeCustom(form) !== null;
  return Boolean(form.secret);
}

function encodeCustom(form: FormState): string | null {
  const headers: Record<string, string> = {};
  for (const row of form.headers) {
    const name = row.name.trim();
    if (name && row.value.trim()) headers[name] = row.value.trim();
  }
  const env: Record<string, string> = {};
  for (const row of form.env) {
    const name = row.name.trim();
    if (name && row.value.trim()) env[name] = row.value.trim();
  }
  const token = form.token.trim();
  if (!token && Object.keys(headers).length === 0 && Object.keys(env).length === 0) return null;
  const body: Record<string, unknown> = {};
  if (token) body.token = token;
  if (Object.keys(headers).length > 0) body.headers = headers;
  if (Object.keys(env).length > 0) body.env = env;
  return JSON.stringify(body);
}

function selectableKinds(group: CredentialGroup): readonly CredentialKind[] {
  if (group === 'mcp') return SELECTABLE_MCP_CREDENTIAL_KINDS;
  return CREDENTIAL_KINDS_BY_GROUP[group];
}

function emptyForm(group: CredentialGroup): FormState {
  return {
    name: '',
    kind: selectableKinds(group)[0],
    secret: '',
    token: '',
    headers: [],
    env: [],
  };
}

export function CredentialsSection() {
  const { t } = useTranslation();
  const { data } = useCredentialsQuery();
  const items = data?.items ?? [];
  const [group, setGroup] = useState<CredentialGroup>('llm');
  const [form, setForm] = useState<FormState | null>(null);
  const [pendingDelete, setPendingDelete] = useState<CredentialListItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function save() {
    if (!form || !form.name.trim()) return;
    setSaving(true);
    try {
      const secret = form.kind === 'custom' ? encodeCustom(form) : form.secret;
      if (form.id) {
        await updateCredential(form.id, {
          name: form.name.trim(),
          kind: form.kind,
          secret: secret || undefined,
        });
        notify({ titleKey: 'settings.notify.credentialUpdated', variant: 'success' });
      } else {
        if (!secret) return;
        await createCredential({ name: form.name.trim(), kind: form.kind, secret });
        notify({ titleKey: 'settings.notify.credentialCreated', variant: 'success' });
      }
      setForm(null);
    } catch (err) {
      const titleKey = err instanceof ApiError && err.messageKey ? err.messageKey : 'settings.notify.saveError';
      notify({ titleKey, variant: 'error' });
    } finally {
      setSaving(false);
    }
  }

  async function remove(item: CredentialListItem) {
    setDeleting(true);
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
    } finally {
      setDeleting(false);
    }
  }

  const kinds = selectableKinds(group);
  const formKinds =
    form && !kinds.includes(form.kind) ? [form.kind, ...kinds] : kinds;
  const visible = items.filter((item) => credentialGroup(item.kind) === group);

  return (
    <div className="max-w-3xl">
      <SectionHeader title={t('settings.nav.credentials')} description={t('settings.credentials.lead')} />
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label={t('settings.credentials.groups')}>
          {CREDENTIAL_GROUPS.map((id) => (
            <Button
              key={id}
              type="button"
              size="sm"
              role="tab"
              variant={group === id ? 'secondary' : 'ghost'}
              aria-selected={group === id}
              onClick={() => setGroup(id)}
            >
              {t(`settings.credentials.group.${id}`)}
            </Button>
          ))}
        </div>
        <Button type="button" onClick={() => setForm(emptyForm(group))}>
          {t('settings.credentials.create')}
        </Button>
      </div>
      {visible.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {items.length === 0 ? t('settings.credentials.empty') : t('settings.credentials.emptyGroup')}
        </p>
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
            {visible.map((item) => (
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
                      setForm({
                        id: item.id,
                        name: item.name,
                        kind: item.kind,
                        secret: '',
                        token: '',
                        headers: [],
                        env: [],
                      })
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
              {form.kind === 'custom' ? (
                <>
                  <p className="text-xs text-muted-foreground">{t('settings.credentials.kindHint.custom')}</p>
                  <div className="grid gap-1.5">
                    <Label htmlFor="cred-bearer">{t('settings.credentials.bearer')}</Label>
                    <Input
                      id="cred-bearer"
                      type="password"
                      autoComplete="new-password"
                      value={form.token}
                      placeholder={form.id ? t('settings.credentials.secretUnchanged') : undefined}
                      onChange={(event) => setForm({ ...form, token: event.target.value })}
                    />
                    <p className="text-xs text-muted-foreground">{t('settings.credentials.bearerHint')}</p>
                  </div>
                  <PairEditor
                    rows={form.headers}
                    nameLabel={t('settings.credentials.headerName')}
                    valueLabel={t('settings.credentials.headerValue')}
                    addLabel={t('settings.credentials.addHeader')}
                    onChange={(headers) => setForm({ ...form, headers })}
                  />
                  <PairEditor
                    rows={form.env}
                    nameLabel={t('settings.credentials.envName')}
                    valueLabel={t('settings.credentials.envValue')}
                    addLabel={t('settings.credentials.addEnv')}
                    onChange={(env) => setForm({ ...form, env })}
                  />
                </>
              ) : (
                <>
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
                        {formKinds.map((kind) => (
                          <SelectItem key={kind} value={kind}>
                            {t(`settings.credentials.kindName.${kind}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">{t(`settings.credentials.kindHint.${form.kind}`)}</p>
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
                </>
              )}
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setForm(null)}>
              {t('settings.common.cancel')}
            </Button>
            <Button
              type="button"
              onClick={() => void save()}
              disabled={!canSave(form)}
              loading={saving}
            >
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
          {pendingDelete?.inUse ? (
            <div className="space-y-2">
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {(pendingDelete.usedBy ?? []).map((label) => (
                  <li key={label}>{usageLabelText(label, t)}</li>
                ))}
              </ul>
              {(pendingDelete.usedBy ?? []).some((label) => label.startsWith('mcp:')) ? (
                <p className="text-sm text-muted-foreground">
                  {t('settings.credentials.inUseMcpHint')}{' '}
                  <Link to="/settings#mcp" className="underline" onClick={() => setPendingDelete(null)}>
                    {t('settings.nav.mcp')}
                  </Link>
                </p>
              ) : null}
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setPendingDelete(null)}>
              {t('settings.common.cancel')}
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={Boolean(pendingDelete?.inUse)}
              loading={deleting}
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
