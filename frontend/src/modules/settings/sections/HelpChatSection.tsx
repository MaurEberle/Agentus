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
  helpChatConfigured,
  isEmbeddingModelName,
  type EmbeddingProvider,
  type HelpProvider,
  type RuntimeModel,
} from '@/modules/settings/model';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';
import { useSettingsDraft } from '@/modules/settings/store';

function RuntimeModelSelect({
  id,
  value,
  models,
  onChange,
  placeholder,
  emptyLabel,
}: {
  id?: string;
  value: string;
  models: RuntimeModel[];
  onChange: (value: string) => void;
  placeholder?: string;
  emptyLabel: string;
}) {
  const names = new Set(models.map((model) => model.name));
  const options = value && !names.has(value) ? [{ name: value }, ...models] : models;

  return (
    <Select value={value || 'none'} onValueChange={(next) => onChange(next === 'none' ? '' : next)}>
      <SelectTrigger id={id}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="none">{emptyLabel}</SelectItem>
        {options.map((model) => (
          <SelectItem key={model.name} value={model.name}>
            {model.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function ModelField({
  id,
  label,
  value,
  models,
  useSelect,
  onChange,
  emptyLabel,
}: {
  id: string;
  label: string;
  value: string;
  models: RuntimeModel[];
  useSelect: boolean;
  onChange: (value: string) => void;
  emptyLabel: string;
}) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {useSelect ? (
        <RuntimeModelSelect
          id={id}
          value={value}
          models={models}
          onChange={onChange}
          placeholder={label}
          emptyLabel={emptyLabel}
        />
      ) : (
        <Input id={id} value={value} onChange={(event) => onChange(event.target.value)} />
      )}
    </div>
  );
}

export function HelpChatSection() {
  const { t } = useTranslation();
  const { data: settings } = useSettingsQuery();
  const { data: credentials } = useCredentialsQuery();
  const { data: models } = useRuntimeModelsQuery();
  const help = useSettingsDraft((state) => state.helpChat);
  const setHelpChat = useSettingsDraft((state) => state.setHelpChat);
  const dirty = useSettingsDraft((state) => state.helpDirty(settings));
  const [pingStatus, setPingStatus] = useState<'unknown' | 'ok' | 'error'>('unknown');
  const [busy, setBusy] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const configured = help ? helpChatConfigured(help) : false;
  const embedChanged =
    Boolean(settings) &&
    Boolean(help) &&
    (help?.embeddingProvider !== settings?.helpChat.embeddingProvider ||
      help?.embeddingModel !== settings?.helpChat.embeddingModel);

  const cloudCredentials = (credentials?.items ?? []).filter(
    (item) => item.kind === 'xai' || item.kind === 'openai_compat',
  );
  const searchCredentials = (credentials?.items ?? []).filter((item) => item.kind === 'web_search');
  const runtimeModels = models?.items ?? [];
  const hasRuntimeModels = runtimeModels.length > 0;
  const embedModels = runtimeModels.filter((model) => isEmbeddingModelName(model.name));
  const emptyLabel = t('settings.helpChat.providerEmpty');

  async function save() {
    if (!help) return;
    setBusy(true);
    try {
      await patchSettings({ helpChat: help });
      notify({ titleKey: 'settings.notify.saved', variant: 'success' });
    } catch {
      notify({ titleKey: 'settings.notify.saveError', variant: 'error' });
    } finally {
      setBusy(false);
    }
  }

  async function runPing() {
    setBusy(true);
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
      setBusy(false);
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
              onValueChange={(value) =>
                setHelpChat({ provider: value === 'none' ? '' : (value as HelpProvider) })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">{t('settings.helpChat.providerEmpty')}</SelectItem>
                <SelectItem value="ollama">Ollama</SelectItem>
                <SelectItem value="xai">xAI</SelectItem>
                <SelectItem value="openai_compat">{t('settings.helpChat.openaiCompat')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <ModelField
            id="help-model"
            label={t('settings.helpChat.model')}
            value={help.model}
            models={runtimeModels}
            useSelect={help.provider === 'ollama' && hasRuntimeModels}
            emptyLabel={emptyLabel}
            onChange={(value) => setHelpChat({ model: value })}
          />
          {help.provider === 'xai' || help.provider === 'openai_compat' ? (
            <div className="grid gap-1.5">
              <Label>{t('settings.helpChat.credential')}</Label>
              <Select
                value={help.credentialId ?? 'none'}
                onValueChange={(value) =>
                  setHelpChat({ credentialId: value === 'none' ? undefined : value })
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
            </div>
          ) : null}
          <div className="grid gap-1.5">
            <Label>{t('settings.helpChat.embedProvider')}</Label>
            <Select
              value={help.embeddingProvider || 'none'}
              onValueChange={(value) =>
                setHelpChat({
                  embeddingProvider: value === 'none' ? '' : (value as EmbeddingProvider),
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">{t('settings.helpChat.providerEmpty')}</SelectItem>
                <SelectItem value="ollama">Ollama</SelectItem>
                <SelectItem value="openai_compat">{t('settings.helpChat.openaiCompat')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <ModelField
            id="embed-model"
            label={t('settings.helpChat.embedModel')}
            value={help.embeddingModel ?? ''}
            models={embedModels}
            useSelect={help.embeddingProvider === 'ollama' && hasRuntimeModels}
            emptyLabel={emptyLabel}
            onChange={(value) => setHelpChat({ embeddingModel: value || undefined })}
          />
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
          <ModelField
            id="fallback-model"
            label={t('settings.helpChat.fallback')}
            value={help.fallbackModel ?? ''}
            models={runtimeModels}
            useSelect={help.provider === 'ollama' && hasRuntimeModels}
            emptyLabel={emptyLabel}
            onChange={(value) => setHelpChat({ fallbackModel: value || undefined })}
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => void save()} disabled={!dirty || busy}>
              {t('settings.common.save')}
            </Button>
            <Button type="button" variant="outline" onClick={() => void runPing()} disabled={busy}>
              {t('settings.helpChat.ping')}
            </Button>
            <Button type="button" variant="outline" onClick={() => setConfirmClear(true)}>
              {t('settings.helpChat.clear')}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                void reindexHelpChat().then((result) =>
                  notify({
                    titleKey: result.state === 'ready' ? 'settings.notify.reindexed' : 'settings.notify.saveError',
                    variant: result.state === 'ready' ? 'success' : 'error',
                  }),
                )
              }
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
