import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ApiError, apiFetch, queryClient } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { notify } from '@/lib/notifications';
import { patchSettings, useCredentialsQuery, useRuntimeModelsQuery, useSettingsQuery } from '@/modules/settings/api';
import {
  credentialMatchesProvider,
  credentialMatchesSearchProvider,
  embeddingNeedsCredential,
  EMBEDDING_PROVIDERS,
  isEmbeddingModelName,
  SEARCH_PROVIDERS,
  type ArchitectSettings,
  type EmbeddingProvider,
} from '@/modules/settings/model';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';

/** What this section edits; model choice and examples live elsewhere. */
type Form = {
  webSearchEnabled: boolean;
  webSearchProvider: string;
  webSearchBaseUrl: string;
  webSearchCredentialId: string;
  sendPathsToCloud: boolean;
  ownNetworksAsExamples: boolean;
  embeddingProvider: EmbeddingProvider;
  embeddingModel: string;
  embeddingCredentialId: string;
  toolCallsPerAnswer: string;
  webSearchesPerSession: string;
  hubCallsPerSession: string;
};

/** Same ranges as the backend (settings/service.py, _ARCHITECT_LIMITS). */
const LIMITS = {
  toolCallsPerAnswer: [5, 100],
  webSearchesPerSession: [0, 200],
  hubCallsPerSession: [0, 300],
} as const;
type LimitKey = keyof typeof LIMITS;

function formFrom(architect: ArchitectSettings | undefined): Form {
  return {
    webSearchEnabled: Boolean(architect?.webSearchEnabled),
    webSearchProvider: architect?.webSearchProvider || 'brave',
    webSearchBaseUrl: architect?.webSearchBaseUrl ?? '',
    webSearchCredentialId: architect?.webSearchCredentialId ?? '',
    sendPathsToCloud: Boolean(architect?.sendPathsToCloud),
    ownNetworksAsExamples: Boolean(architect?.ownNetworksAsExamples),
    embeddingProvider: architect?.embeddingProvider ?? '',
    embeddingModel: architect?.embeddingModel ?? '',
    embeddingCredentialId: architect?.embeddingCredentialId ?? '',
    toolCallsPerAnswer: String(architect?.toolCallsPerAnswer ?? 25),
    webSearchesPerSession: String(architect?.webSearchesPerSession ?? 20),
    hubCallsPerSession: String(architect?.hubCallsPerSession ?? 30),
  };
}

type ExampleStatus = {
  count: number;
  shipped: number;
  own: number;
  ownEnabled: boolean;
  model: string | null;
  embedded: number;
  method: 'embedding' | 'keywords';
  error?: string | null;
};

const EXAMPLES_KEY = ['architect', 'examples'] as const;

function limitValid(key: LimitKey, raw: string): boolean {
  const value = Number(raw);
  const [low, high] = LIMITS[key];
  return raw.trim() !== '' && Number.isInteger(value) && value >= low && value <= high;
}

/** Einstellungen → Architekt (netz-architekt 13): own web search, cloud rule for paths, limits. */
export function ArchitectSection() {
  const { t } = useTranslation();
  const { data: settings } = useSettingsQuery();
  const { data: credentials } = useCredentialsQuery();
  const stored = useMemo(() => formFrom(settings?.architect), [settings?.architect]);
  const [form, setForm] = useState<Form>(stored);
  const [saving, setSaving] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const examples = useQuery({
    queryKey: EXAMPLES_KEY,
    queryFn: () => apiFetch<ExampleStatus>('/architect/examples'),
  });
  const runtime = useRuntimeModelsQuery({ enabled: form.embeddingProvider === 'ollama' });
  const embedModels = (runtime.data?.items ?? []).filter((item) => isEmbeddingModelName(item.name));
  const embedCredentials = (credentials?.items ?? []).filter((item) =>
    credentialMatchesProvider(item.kind, form.embeddingProvider),
  );

  useEffect(() => setForm(stored), [stored]);

  const set = (patch: Partial<Form>) => setForm((current) => ({ ...current, ...patch }));
  const searchCredentials = (credentials?.items ?? []).filter((item) =>
    credentialMatchesSearchProvider(item.kind, form.webSearchProvider),
  );
  const limitsValid = (Object.keys(LIMITS) as LimitKey[]).every((key) => limitValid(key, form[key]));
  const dirty = JSON.stringify(form) !== JSON.stringify(stored);
  // Not repeated when the "credential missing" line already says it.
  const searchIncomplete =
    form.webSearchEnabled &&
    (form.webSearchProvider === 'searxng'
      ? !form.webSearchBaseUrl.trim()
      : searchCredentials.length > 0 && !form.webSearchCredentialId);

  async function save() {
    if (!limitsValid) return;
    setSaving(true);
    try {
      await patchSettings({
        architect: {
          webSearchEnabled: form.webSearchEnabled,
          webSearchProvider: form.webSearchProvider,
          webSearchBaseUrl: form.webSearchProvider === 'searxng' ? form.webSearchBaseUrl.trim() || null : null,
          webSearchCredentialId: form.webSearchProvider === 'searxng' ? null : form.webSearchCredentialId || null,
          sendPathsToCloud: form.sendPathsToCloud,
          ownNetworksAsExamples: form.ownNetworksAsExamples,
          embeddingProvider: form.embeddingProvider,
          embeddingModel: form.embeddingProvider ? form.embeddingModel.trim() : '',
          embeddingCredentialId: embeddingNeedsCredential(form.embeddingProvider) ? form.embeddingCredentialId || null : null,
          toolCallsPerAnswer: Number(form.toolCallsPerAnswer),
          webSearchesPerSession: Number(form.webSearchesPerSession),
          hubCallsPerSession: Number(form.hubCallsPerSession),
        } as ArchitectSettings,
      });
      notify({ titleKey: 'settings.notify.saved', variant: 'success' });
      void queryClient.invalidateQueries({ queryKey: EXAMPLES_KEY });
    } catch (error) {
      notify({
        titleKey: error instanceof ApiError && error.messageKey === 'settings.architect.limit' ? 'settings.architect.limitError' : 'settings.notify.saveError',
        variant: 'error',
      });
    } finally {
      setSaving(false);
    }
  }

  async function rebuildExamples() {
    setReindexing(true);
    try {
      const next = await apiFetch<ExampleStatus>('/architect/examples/reindex', { method: 'POST' });
      queryClient.setQueryData(EXAMPLES_KEY, next);
      notify({
        titleKey: next.error ? 'settings.architect.examples.reindexFailed' : 'settings.architect.examples.reindexDone',
        variant: next.error ? 'warning' : 'success',
      });
    } catch {
      notify({ titleKey: 'settings.architect.examples.reindexFailed', variant: 'error' });
    } finally {
      setReindexing(false);
    }
  }

  const status = examples.data;

  return (
    <div className="max-w-2xl space-y-6">
      <SectionHeader title={t('settings.nav.architect')} description={t('settings.architect.lead')} />

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3 rounded-md border p-3">
          <div>
            <Label htmlFor="architect-web-search" className="text-sm font-medium">
              {t('settings.architect.webSearch')}
            </Label>
            <p className="text-xs text-muted-foreground">{t('settings.architect.webSearchHint')}</p>
          </div>
          <Switch
            id="architect-web-search"
            checked={form.webSearchEnabled}
            onCheckedChange={(checked) => set({ webSearchEnabled: checked })}
          />
        </div>
        {form.webSearchEnabled ? (
          <div className="grid gap-3 ps-1">
            <div className="grid gap-1.5">
              <Label>{t('settings.helpChat.webSearchProvider')}</Label>
              <Select
                value={form.webSearchProvider}
                onValueChange={(value) => {
                  const keep = (credentials?.items ?? []).some(
                    (item) => item.id === form.webSearchCredentialId && credentialMatchesSearchProvider(item.kind, value),
                  );
                  set({ webSearchProvider: value, webSearchCredentialId: keep ? form.webSearchCredentialId : '' });
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SEARCH_PROVIDERS.map((item) => (
                    <SelectItem key={item} value={item}>
                      {t(`network.inspector.tool.searchProviderName.${item}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {form.webSearchProvider === 'searxng' ? (
              <div className="grid gap-1.5">
                <Label htmlFor="architect-searxng">{t('settings.helpChat.webSearchBaseUrl')}</Label>
                <Input
                  id="architect-searxng"
                  value={form.webSearchBaseUrl}
                  spellCheck={false}
                  autoComplete="off"
                  placeholder="https://"
                  onChange={(event) => set({ webSearchBaseUrl: event.target.value })}
                />
              </div>
            ) : (
              <div className="grid gap-1.5">
                <Label>{t('settings.helpChat.webSearchCredential')}</Label>
                {searchCredentials.length === 0 ? (
                  <p className="text-sm text-destructive">{t('settings.helpChat.webSearchMissing')}</p>
                ) : (
                  <Select
                    value={form.webSearchCredentialId || 'none'}
                    onValueChange={(value) => set({ webSearchCredentialId: value === 'none' ? '' : value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">{t('settings.helpChat.credentialEmpty')}</SelectItem>
                      {searchCredentials.map((item) => (
                        <SelectItem key={item.id} value={item.id}>
                          {item.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>
            )}
            {searchIncomplete ? <p className="text-xs text-warning">{t('settings.architect.webSearchIncomplete')}</p> : null}
          </div>
        ) : null}
      </section>

      <section className="flex items-center justify-between gap-3 rounded-md border p-3">
        <div>
          <Label htmlFor="architect-paths" className="text-sm font-medium">
            {t('settings.architect.sendPaths')}
          </Label>
          <p className="text-xs text-muted-foreground">{t('settings.architect.sendPathsHint')}</p>
        </div>
        <Switch
          id="architect-paths"
          checked={form.sendPathsToCloud}
          onCheckedChange={(checked) => set({ sendPathsToCloud: checked })}
        />
      </section>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">{t('settings.architect.examples.title')}</legend>
        <p className="text-xs text-muted-foreground">{t('settings.architect.examples.hint')}</p>
        <div className="flex items-center justify-between gap-3 rounded-md border p-3">
          <div>
            <Label htmlFor="architect-own-examples" className="text-sm font-medium">
              {t('settings.architect.examples.own')}
            </Label>
            <p className="text-xs text-muted-foreground">{t('settings.architect.examples.ownHint')}</p>
          </div>
          <Switch
            id="architect-own-examples"
            checked={form.ownNetworksAsExamples}
            onCheckedChange={(checked) => set({ ownNetworksAsExamples: checked })}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid content-start gap-1.5">
            <Label>{t('settings.architect.examples.embeddingProvider')}</Label>
            <Select
              value={form.embeddingProvider || 'none'}
              onValueChange={(value) =>
                set({
                  embeddingProvider: (value === 'none' ? '' : value) as EmbeddingProvider,
                  embeddingModel: '',
                  embeddingCredentialId: '',
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">{t('settings.architect.examples.keywordsOnly')}</SelectItem>
                {EMBEDDING_PROVIDERS.map((item) => (
                  <SelectItem key={item} value={item}>
                    {t(`providers.${item}`, { defaultValue: item })}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {form.embeddingProvider ? (
            <div className="grid content-start gap-1.5">
              <Label htmlFor="architect-embed-model">{t('settings.architect.examples.embeddingModel')}</Label>
              <Input
                id="architect-embed-model"
                value={form.embeddingModel}
                list="architect-embed-models"
                spellCheck={false}
                autoComplete="off"
                placeholder={form.embeddingProvider === 'ollama' ? 'nomic-embed-text' : 'text-embedding-3-small'}
                onChange={(event) => set({ embeddingModel: event.target.value })}
              />
              <datalist id="architect-embed-models">
                {embedModels.map((item) => (
                  <option key={item.name} value={item.name} />
                ))}
              </datalist>
            </div>
          ) : null}
          {embeddingNeedsCredential(form.embeddingProvider) ? (
            <div className="grid content-start gap-1.5">
              <Label>{t('settings.helpChat.credential')}</Label>
              <Select
                value={form.embeddingCredentialId || 'none'}
                onValueChange={(value) => set({ embeddingCredentialId: value === 'none' ? '' : value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">{t('settings.helpChat.credentialEmpty')}</SelectItem>
                  {embedCredentials.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/40 px-3 py-2 text-xs">
          <span className="text-muted-foreground">
            {status
              ? [
                  t('settings.architect.examples.count', { count: status.count, shipped: status.shipped, own: status.own }),
                  status.method === 'embedding' && status.model
                    ? t('settings.architect.examples.embedded', { model: status.model, done: status.embedded, count: status.count })
                    : t('settings.architect.examples.keywords'),
                ].join(' · ')
              : t('settings.architect.examples.loading')}
          </span>
          <Button type="button" size="sm" variant="outline" loading={reindexing} disabled={reindexing || dirty} onClick={() => void rebuildExamples()}>
            {t('settings.architect.examples.reindex')}
          </Button>
        </div>
        {dirty ? <p className="text-xs text-muted-foreground">{t('settings.architect.examples.saveFirst')}</p> : null}
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">{t('settings.architect.limits')}</legend>
        <p className="text-xs text-muted-foreground">{t('settings.architect.limitsHint')}</p>
        <div className="grid gap-3 sm:grid-cols-3">
          {(Object.keys(LIMITS) as LimitKey[]).map((key) => {
            const valid = limitValid(key, form[key]);
            const [low, high] = LIMITS[key];
            return (
              <div key={key} className="grid content-start gap-1.5">
                <Label htmlFor={`architect-${key}`}>{t(`settings.architect.limit.${key}`)}</Label>
                <Input
                  id={`architect-${key}`}
                  type="number"
                  inputMode="numeric"
                  min={low}
                  max={high}
                  step={1}
                  className="w-28"
                  value={form[key]}
                  aria-invalid={!valid}
                  onChange={(event) => set({ [key]: event.target.value } as Partial<Form>)}
                />
                <p className={valid ? 'text-xs text-muted-foreground' : 'text-xs text-destructive'}>
                  {t('settings.architect.range', { min: low, max: high })}
                </p>
              </div>
            );
          })}
        </div>
      </fieldset>

      <div className="flex flex-wrap gap-2">
        <Button type="button" onClick={() => void save()} disabled={!dirty || saving || !limitsValid} loading={saving}>
          {t('settings.common.save')}
        </Button>
        <Button type="button" variant="outline" disabled={!dirty || saving} onClick={() => setForm(stored)}>
          {t('settings.architect.reset')}
        </Button>
      </div>
    </div>
  );
}
