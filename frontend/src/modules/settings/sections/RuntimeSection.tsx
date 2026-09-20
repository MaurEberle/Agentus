import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { notify } from '@/lib/notifications';
import { patchSettings, pingRuntime, useRuntimeModelsQuery, useSettingsQuery } from '@/modules/settings/api';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';
import { useSettingsDraft } from '@/modules/settings/store';

function formatBytes(bytes?: number): string {
  if (!bytes) return '—';
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function RuntimeSection() {
  const { t } = useTranslation();
  const { data: settings } = useSettingsQuery();
  const { data: models } = useRuntimeModelsQuery();
  const runtime = useSettingsDraft((state) => state.runtime);
  const setRuntime = useSettingsDraft((state) => state.setRuntime);
  const syncRuntime = useSettingsDraft((state) => state.syncRuntime);
  const dirty = useSettingsDraft((state) => state.runtimeDirty(settings));
  const [pingStatus, setPingStatus] = useState<'unknown' | 'ok' | 'error'>('unknown');
  const [pinging, setPinging] = useState(false);
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!runtime) return;
    setSaving(true);
    try {
      const next = await patchSettings({
        ollamaBaseUrl: runtime.ollamaBaseUrl.trim(),
        openaiCompatBaseUrl: runtime.openaiCompatBaseUrl.trim(),
      });
      syncRuntime(next);
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
      const result = await pingRuntime();
      setPingStatus(result.ok ? 'ok' : 'error');
      notify({
        titleKey: result.messageKey ?? (result.ok ? 'settings.runtime.pingOk' : 'settings.runtime.pingFail'),
        variant: result.ok ? 'success' : 'error',
      });
    } catch {
      setPingStatus('error');
      notify({ titleKey: 'settings.runtime.pingFail', variant: 'error' });
    } finally {
      setPinging(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <SectionHeader title={t('settings.nav.runtime')} description={t('settings.runtime.lead')} />
      <div className="grid gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor="ollama-url">{t('settings.runtime.ollamaUrl')}</Label>
          <Input
            id="ollama-url"
            placeholder="http://127.0.0.1:11434"
            value={runtime?.ollamaBaseUrl ?? ''}
            onChange={(event) => setRuntime({ ollamaBaseUrl: event.target.value })}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="compat-url">{t('settings.runtime.openaiCompatUrl')}</Label>
          <Input
            id="compat-url"
            placeholder="http://127.0.0.1:1234/v1"
            value={runtime?.openaiCompatBaseUrl ?? ''}
            onChange={(event) => setRuntime({ openaiCompatBaseUrl: event.target.value })}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" onClick={() => void save()} disabled={!dirty || saving}>
            {t('settings.common.save')}
          </Button>
          <Button type="button" variant="outline" onClick={() => void runPing()} disabled={pinging}>
            {t('settings.runtime.ping')}
          </Button>
          <Badge variant={pingStatus === 'ok' ? 'default' : pingStatus === 'error' ? 'destructive' : 'secondary'}>
            {t(`settings.runtime.status.${pingStatus}`)}
          </Badge>
        </div>
      </div>
      <div>
        <h2 className="mb-2 text-sm font-medium">{t('settings.runtime.models')}</h2>
        {(models?.items.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">{t('settings.runtime.modelsEmpty')}</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('settings.runtime.modelName')}</TableHead>
                <TableHead>{t('settings.runtime.modelSize')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {models?.items.map((model) => (
                <TableRow key={model.name}>
                  <TableCell className="font-mono text-xs">{model.name}</TableCell>
                  <TableCell>{formatBytes(model.sizeBytes)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
