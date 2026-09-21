import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription } from '@/components/ui/alert';
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
import { Switch } from '@/components/ui/switch';
import { ModelCombobox } from '@/components/ModelCombobox';
import i18n from '@/i18n';
import { notify } from '@/lib/notifications';
import {
  clearHelpChatMessages,
  patchSettings,
  pingHelpChat,
  reindexHelpChat,
  resetHelpChatOnboarding,
  useCredentialsQuery,
  useRuntimeModelsQuery,
  useSettingsQuery,
} from '@/modules/settings/api';
import {
  EMBEDDING_PROVIDERS,
  LLM_PROVIDERS,
  credentialMatchesProvider,
  embeddingNeedsCredential,
  helpChatConfigured,
  helpChatWritePayload,
  isCloudCatalogProvider,
  isEmbeddingModelName,
  type EmbeddingProvider,
  type HelpChatSettings,
  type HelpProvider,
  type LlmProvider,
  type RuntimeModel,
} from '@/modules/settings/model';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';
import { useSettingsDraft } from '@/modules/settings/store';

function ModelField({
  id,
  label,
  value,
  models,
  useSelect,
  onChange,
  emptyLabel,
  disabled,
  placeholder,
}: {
  id: string;
  label: string;
  value: string;
  models: RuntimeModel[];
  useSelect: boolean;
  onChange: (value: string) => void;
  emptyLabel: string;
  disabled?: boolean;
  placeholder?: string;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid min-w-0 gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {useSelect ? (
        <ModelCombobox
          id={id}
          value={value}
          options={models.map((model) => model.name)}
          onChange={onChange}
          placeholder={placeholder ?? label}
          emptyLabel={emptyLabel}
          noModelsLabel={t('network.inspector.llm.noModels')}
          useValueLabel={(name) => t('network.inspector.llm.useModel', { name })}
          disabled={disabled}
        />
      ) : (
        <Input
          id={id}
          value={value}
          disabled={disabled}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </div>
  );
}

export function HelpChatSection() {
  const { t } = useTranslation();
  const { data: settings } = useSettingsQuery();
  const { data: credentials } = useCredentialsQuery();
  const help = useSettingsDraft((state) => state.helpChat);
  const setHelpChat = useSettingsDraft((state) => state.setHelpChat);
  const syncHelpChat = useSettingsDraft((state) => state.syncHelpChat);
  const { data: models } = useRuntimeModelsQuery();
  const catalogQuery = useRuntimeModelsQuery({
    provider: (help?.provider || 'ollama') as LlmProvider,
    credentialId: help?.credentialId,
    enabled: isCloudCatalogProvider(help?.provider ?? '') && Boolean(help?.credentialId),
  });
  const embedCatalogQuery = useRuntimeModelsQuery({
    provider: (help?.embeddingProvider || 'ollama') as LlmProvider,
    credentialId: help?.embeddingCredentialId,
    enabled: embeddingNeedsCredential(help?.embeddingProvider ?? '') && Boolean(help?.embeddingCredentialId),
  });
  const dirty = useSettingsDraft((state) => state.helpDirty(settings));
  const [pingStatus, setPingStatus] = useState<'unknown' | 'ok' | 'error'>('unknown');
  const [saving, setSaving] = useState(false);
  const [pinging, setPinging] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const configured = help ? helpChatConfigured(help) : false;
  const embedChanged =
    Boolean(settings) &&
    Boolean(help) &&
    (help?.embeddingProvider !== settings?.helpChat.embeddingProvider ||
      help?.embeddingModel !== settings?.helpChat.embeddingModel ||
      (help?.embeddingCredentialId || '') !== (settings?.helpChat.embeddingCredentialId || ''));

  const cloudCredentials = (credentials?.items ?? []).filter((item) =>
    credentialMatchesProvider(item.kind, help?.provider ?? ''),
  );
  const kindCredentials = (credentials?.items ?? []).filter((item) => item.kind === help?.provider);
  const searchCredentials = (credentials?.items ?? []).filter((item) => item.kind === 'web_search');
  const runtimeModels = models?.items ?? [];
  const hasRuntimeModels = runtimeModels.length > 0;
  const embedModels = runtimeModels.filter((model) => isEmbeddingModelName(model.name));
  const catalogModels = catalogQuery.data?.items ?? [];
  const embedCatalogModels = (embedCatalogQuery.data?.items ?? []).filter((model) =>
    isEmbeddingModelName(model.name),
  );
  const emptyLabel = t('settings.helpChat.providerEmpty');
  const catalogLocked = isCloudCatalogProvider(help?.provider ?? '') && !help?.credentialId;
  const catalogFailed =
    isCloudCatalogProvider(help?.provider ?? '') &&
    Boolean(help?.credentialId) &&
    !catalogQuery.isFetching &&
    !catalogQuery.isPending &&
    catalogModels.length === 0;
  const embedLocked = embeddingNeedsCredential(help?.embeddingProvider ?? '') && !help?.embeddingCredentialId;
  const embedCatalogFailed =
    embeddingNeedsCredential(help?.embeddingProvider ?? '') &&
    Boolean(help?.embeddingCredentialId) &&
    !embedCatalogQuery.isFetching &&
    !embedCatalogQuery.isPending &&
    embedCatalogModels.length === 0;
  const embedKindCredentials = (credentials?.items ?? []).filter(
    (item) => item.kind === help?.embeddingProvider,
  );
  const embedCredentials = (credentials?.items ?? []).filter((item) =>
    credentialMatchesProvider(item.kind, help?.embeddingProvider ?? ''),
  );

  async function save() {
    if (!help) return;
    setSaving(true);
    try {
      const next = await patchSettings({
        helpChat: helpChatWritePayload(help) as HelpChatSettings,
      });
      syncHelpChat(next);
      notify({ titleKey: 'settings.notify.saved', variant: 'success' });
    } catch {
      notify({ titleKey: 'settings.notify.saveError', variant: 'error' });
    } finally {
      setSaving(false);
    }
  }

  async function runPing() {
    setPinging(true);
    try {
      const result = await pingHelpChat();
      setPingStatus(result.ok ? 'ok' : 'error');
      notify({
        titleKey: result.messageKey ?? (result.ok ? 'settings.helpChat.pingOk' : 'settings.helpChat.pingFail'),
        variant: result.ok ? 'success' : 'error',
      });
    } catch {
      setPingStatus('error');
      notify({ titleKey: 'settings.helpChat.pingFail', variant: 'error' });
    } finally {
      setPinging(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <SectionHeader title={t('settings.nav.help-chat')} description={t('settings.helpChat.lead')} />
      <div className="flex items-center gap-2">
        <Badge variant={configured ? 'default' : 'secondary'}>
          {configured ? t('settings.helpChat.configured') : t('settings.helpChat.incomplete')}
        </Badge>
        <Badge variant={pingStatus === 'ok' ? 'default' : pingStatus === 'error' ? 'destructive' : 'secondary'}>
          {t(`settings.runtime.status.${pingStatus}`)}
        </Badge>
      </div>
      {help ? (
        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <Label>{t('settings.helpChat.provider')}</Label>
            <Select
              value={help.provider || 'none'}
              onValueChange={(value) => {
                const next = value === 'none' ? '' : (value as HelpProvider);
                const patch: Partial<typeof help> = { provider: next };
                if (next !== help.provider) {
                  patch.model = '';
                }
                if (next === 'ollama' || next === '') {
                  patch.credentialId = undefined;
                } else if (isCloudCatalogProvider(next)) {
                  const nextKind = (credentials?.items ?? []).filter((item) => item.kind === next);
                  const current = (credentials?.items ?? []).find((item) => item.id === help.credentialId);
                  if (!current || !credentialMatchesProvider(current.kind, next)) {
                    patch.credentialId = nextKind.length === 1 ? nextKind[0].id : undefined;
                  }
                }
                setHelpChat(patch);
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">{t('settings.helpChat.providerEmpty')}</SelectItem>
                {LLM_PROVIDERS.map((id) => (
                  <SelectItem key={id} value={id}>
                    {t(`providers.${id}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {isCloudCatalogProvider(help.provider) ? (
            <div className="grid gap-1.5">
              <Label>{t('settings.helpChat.credential')}</Label>
              <Select
                value={help.credentialId ?? 'none'}
                onValueChange={(value) =>
                  setHelpChat({
                    credentialId: value === 'none' ? undefined : value,
                    model: '',
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">{t('settings.helpChat.credentialEmpty')}</SelectItem>
                  {cloudCredentials.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {kindCredentials.length === 0 ? (
                <p className="text-xs text-destructive">{t('settings.helpChat.noCredentials')}</p>
              ) : (
                <p className="text-xs text-muted-foreground">{t('settings.helpChat.credentialHint')}</p>
              )}
            </div>
          ) : null}
          <ModelField
            id="help-model"
            label={t('settings.helpChat.model')}
            value={catalogLocked ? '' : help.model}
            models={
              isCloudCatalogProvider(help.provider)
                ? catalogModels.filter((model) => !isEmbeddingModelName(model.name))
                : runtimeModels
            }
            useSelect={
              (help.provider === 'ollama' && hasRuntimeModels) ||
              (isCloudCatalogProvider(help.provider) && Boolean(help.credentialId))
            }
            emptyLabel={emptyLabel}
            disabled={catalogLocked}
            placeholder={catalogLocked ? t('settings.helpChat.pickCredentialFirst') : undefined}
            onChange={(value) => setHelpChat({ model: value })}
          />
          {catalogFailed ? (
            <p className="text-xs text-destructive">{t('settings.helpChat.modelsLoadError')}</p>
          ) : null}
          {help.provider === 'ollama' ? (
            <ModelField
              id="fallback-model"
              label={t('settings.helpChat.fallback')}
              value={help.fallbackModel ?? ''}
              models={runtimeModels.filter((model) => !isEmbeddingModelName(model.name))}
              useSelect={hasRuntimeModels}
              emptyLabel={emptyLabel}
              onChange={(value) => setHelpChat({ fallbackModel: value || undefined })}
            />
          ) : null}
          <div className="grid gap-1.5">
            <Label>{t('settings.helpChat.embedProvider')}</Label>
            <Select
              value={help.embeddingProvider || 'none'}
              onValueChange={(value) => {
                const next = value === 'none' ? '' : (value as EmbeddingProvider);
                const patch: Partial<typeof help> = {
                  embeddingProvider: next,
                  embeddingModel: '',
                };
                if (!embeddingNeedsCredential(next)) {
                  patch.embeddingCredentialId = undefined;
                } else {
                  const nextKind = (credentials?.items ?? []).filter((item) => item.kind === next);
                  const current = (credentials?.items ?? []).find(
                    (item) => item.id === help.embeddingCredentialId,
                  );
                  if (!current || !credentialMatchesProvider(current.kind, next)) {
                    if (help.provider === next && help.credentialId) {
                      patch.embeddingCredentialId = help.credentialId;
                    } else {
                      patch.embeddingCredentialId = nextKind.length === 1 ? nextKind[0].id : undefined;
                    }
                  }
                }
                setHelpChat(patch);
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">{t('settings.helpChat.providerEmpty')}</SelectItem>
                {EMBEDDING_PROVIDERS.map((id) => (
                  <SelectItem key={id} value={id}>
                    {t(`providers.${id}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {embeddingNeedsCredential(help.embeddingProvider || '') ? (
            <div className="grid gap-1.5">
              <Label>{t('settings.helpChat.credential')}</Label>
              <Select
                value={help.embeddingCredentialId ?? 'none'}
                onValueChange={(value) =>
                  setHelpChat({
                    embeddingCredentialId: value === 'none' ? undefined : value,
                    embeddingModel: '',
                  })
                }
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
              {embedKindCredentials.length === 0 ? (
                <p className="text-xs text-destructive">{t('settings.helpChat.noCredentials')}</p>
              ) : (
                <p className="text-xs text-muted-foreground">{t('settings.helpChat.credentialHint')}</p>
              )}
            </div>
          ) : null}
          <ModelField
            id="embed-model"
            label={t('settings.helpChat.embedModel')}
            value={embedLocked ? '' : (help.embeddingModel ?? '')}
            models={
              embeddingNeedsCredential(help.embeddingProvider || '') ? embedCatalogModels : embedModels
            }
            useSelect={
              (help.embeddingProvider === 'ollama' && hasRuntimeModels) ||
              (embeddingNeedsCredential(help.embeddingProvider || '') && Boolean(help.embeddingCredentialId))
            }
            emptyLabel={emptyLabel}
            disabled={embedLocked}
            placeholder={embedLocked ? t('settings.helpChat.pickCredentialFirst') : undefined}
            onChange={(value) => setHelpChat({ embeddingModel: value || undefined })}
          />
          {embedCatalogFailed ? (
            <p className="text-xs text-destructive">{t('settings.helpChat.modelsLoadError')}</p>
          ) : null}
          {embedChanged ? (
            <Alert>
              <AlertDescription>{t('settings.helpChat.reindexHint')}</AlertDescription>
            </Alert>
          ) : null}
          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">{t('settings.helpChat.webSearch')}</p>
              <p className="text-xs text-muted-foreground">{t('settings.helpChat.webSearchHint')}</p>
            </div>
            <Switch
              checked={help.webSearchEnabled}
              onCheckedChange={(checked) => setHelpChat({ webSearchEnabled: checked })}
            />
          </div>
          {help.webSearchEnabled ? (
            <div className="grid gap-1.5">
              <Label>{t('settings.helpChat.webSearchCredential')}</Label>
              {searchCredentials.length === 0 ? (
                <p className="text-sm text-destructive">{t('settings.helpChat.webSearchMissing')}</p>
              ) : (
                <Select
                  value={help.webSearchCredentialId ?? 'none'}
                  onValueChange={(value) =>
                    setHelpChat({ webSearchCredentialId: value === 'none' ? undefined : value })
                  }
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
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => void save()} disabled={!dirty || saving} loading={saving}>
              {t('settings.common.save')}
            </Button>
            <Button type="button" variant="outline" onClick={() => void runPing()} disabled={pinging} loading={pinging}>
              {t('settings.helpChat.ping')}
            </Button>
            <Button type="button" variant="outline" onClick={() => setConfirmClear(true)}>
              {t('settings.helpChat.clear')}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={reindexing}
              loading={reindexing}
              onClick={() => {
                setReindexing(true);
                void reindexHelpChat()
                  .then((result) => {
                    const failed = result.state !== 'ready';
                    const reported = result.messageKey;
                    notify({
                      titleKey:
                        !failed
                          ? 'settings.notify.reindexed'
                          : reported && i18n.exists(reported)
                            ? reported
                            : 'help.index.failed',
                      variant: failed ? 'error' : 'success',
                    });
                  })
                  .catch(() => notify({ titleKey: 'help.index.failed', variant: 'error' }))
                  .finally(() => setReindexing(false));
              }}
            >
              {t('settings.helpChat.reindex')}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() =>
                void resetHelpChatOnboarding().then(() =>
                  notify({ titleKey: 'settings.notify.onboardingReset', variant: 'info' }),
                )
              }
            >
              {t('settings.helpChat.resetOnboarding')}
            </Button>
          </div>
        </div>
      ) : null}

      <Dialog open={confirmClear} onOpenChange={setConfirmClear}>
        <DialogContent closeLabel={t('settings.common.close')}>
          <DialogHeader>
            <DialogTitle>{t('settings.helpChat.clearTitle')}</DialogTitle>
            <DialogDescription>{t('settings.helpChat.clearBody')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConfirmClear(false)}>
              {t('settings.common.cancel')}
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() =>
                void clearHelpChatMessages().then(() => {
                  setConfirmClear(false);
                  notify({ titleKey: 'settings.notify.helpCleared', variant: 'success' });
                })
              }
            >
              {t('settings.helpChat.clear')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
