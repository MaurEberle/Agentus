import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Play, Square } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ModelCombobox } from '@/components/ModelCombobox';
import { formatBytes } from '@/lib/format';
import { modelFactsMap } from '@/lib/modelName';
import { checkModel, type ArchitectStatus, type GpuCheck, type ModelCheck } from '@/modules/architect/api';
import { useArchitectUi, type ModelPick } from '@/modules/architect/store';
import { listInstalled } from '@/modules/models/api';
import {
  LLM_PROVIDERS,
  credentialMatchesProvider,
  isCloudCatalogProvider,
  type LlmProvider,
} from '@/modules/settings/model';
import { useCredentialsQuery, useRuntimeModelsQuery, useSettingsQuery } from '@/modules/settings/api';

const MIN_B = 4;

function parametersB(raw: string | undefined): number | null {
  const text = (raw ?? '').trim().toUpperCase();
  const value = Number.parseFloat(text);
  if (!Number.isFinite(value)) return null;
  if (text.endsWith('M')) return value / 1000;
  return text.endsWith('B') ? value : null;
}

/** Provider, credential and model for the architect; start and stop; the check before a start. */
export function ModelBar({
  status,
  sessionActive,
  busy,
  onStart,
  onStop,
}: {
  status: ArchitectStatus | undefined;
  sessionActive: boolean;
  busy: boolean;
  onStart: (pick: ModelPick) => void;
  onStop: () => void;
}) {
  const { t, i18n } = useTranslation();
  const pick = useArchitectUi((state) => state.pick);
  const setPick = useArchitectUi((state) => state.setPick);
  const { data: settings } = useSettingsQuery();
  const { data: credentials } = useCredentialsQuery();
  const installed = useQuery({ queryKey: ['models'], queryFn: listInstalled, gcTime: Number.POSITIVE_INFINITY });
  const current: ModelPick = pick ?? { provider: '', model: '', credentialId: null };

  useEffect(() => {
    if (pick || !settings) return;
    const last = settings.architect;
    setPick({
      provider: (last?.provider || 'ollama') as LlmProvider,
      model: last?.model ?? '',
      credentialId: last?.credentialId ?? null,
    });
  }, [pick, settings, setPick]);

  const cloud = isCloudCatalogProvider(current.provider);
  const catalog = useRuntimeModelsQuery({
    provider: (current.provider || 'ollama') as LlmProvider,
    credentialId: current.credentialId ?? undefined,
    enabled: cloud && Boolean(current.credentialId),
  });
  const local = current.provider === 'ollama';
  const localModels = useMemo(
    () => (installed.data?.items ?? []).filter((item) => item.kind !== 'embedding' && item.kind !== 'image'),
    [installed.data],
  );
  const cloudModels = useMemo(() => (catalog.data && 'items' in catalog.data ? catalog.data.items : []), [catalog.data]);
  const options = local ? localModels.map((item) => item.name) : cloudModels.map((item) => item.name);
  const facts = useMemo(() => (local ? undefined : modelFactsMap(cloudModels)), [local, cloudModels]);

  function blocked(name: string): string | null {
    if (!local) return null;
    const item = localModels.find((row) => row.name === name);
    if (!item) return null;
    if (!item.tools) return t('architect.model.noToolsShort');
    const size = parametersB(item.parameterSize);
    if (size !== null && size < MIN_B) return t('architect.model.tooSmallShort');
    return null;
  }

  const [check, setCheck] = useState<{ model: ModelCheck; gpu?: GpuCheck } | null>(null);
  const checkInput = useMemo(
    () => ({ provider: current.provider, model: current.model, credentialId: current.credentialId }),
    [current.provider, current.model, current.credentialId],
  );
  useEffect(() => {
    setCheck(null);
    if (!checkInput.provider || !checkInput.model.trim() || sessionActive) return undefined;
    let stale = false;
    const timer = window.setTimeout(() => {
      void checkModel(checkInput)
        .then((result) => {
          if (!stale) setCheck(result);
        })
        .catch(() => undefined);
    }, 250);
    return () => {
      stale = true;
      window.clearTimeout(timer);
    };
  }, [checkInput, sessionActive]);

  const kindCredentials = (credentials?.items ?? []).filter((item) => credentialMatchesProvider(item.kind, current.provider));
  const active = status?.active;
  const canStart = Boolean(current.provider && current.model.trim()) && (check?.model.ok ?? false) && !busy;

  return (
    <div className="flex flex-wrap items-end gap-x-3 gap-y-2 border-b px-3 py-2">
      <div className="grid gap-1">
        <span className="text-xs text-muted-foreground">{t('architect.model.provider')}</span>
        <Select
          value={current.provider || 'ollama'}
          disabled={sessionActive}
          onValueChange={(value) => {
            const next = value as LlmProvider;
            const matching = (credentials?.items ?? []).filter((item) => credentialMatchesProvider(item.kind, next));
            setPick({ provider: next, model: '', credentialId: next === 'ollama' ? null : matching.length === 1 ? matching[0].id : null });
          }}
        >
          <SelectTrigger className="h-8 w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {LLM_PROVIDERS.map((id) => (
              <SelectItem key={id} value={id}>
                {t(`providers.${id}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {cloud ? (
        <div className="grid gap-1">
          <span className="text-xs text-muted-foreground">{t('architect.model.credential')}</span>
          <Select
            value={current.credentialId ?? 'none'}
            disabled={sessionActive}
            onValueChange={(value) => setPick({ ...current, credentialId: value === 'none' ? null : value, model: '' })}
          >
            <SelectTrigger className="h-8 w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">{t('architect.model.credentialNone')}</SelectItem>
              {kindCredentials.map((item) => (
                <SelectItem key={item.id} value={item.id}>
                  {item.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
      <div className="grid min-w-56 flex-1 gap-1 sm:max-w-80">
        <span className="text-xs text-muted-foreground">{t('architect.model.model')}</span>
        <ModelCombobox
          value={current.model}
          options={options}
          facts={facts}
          blocked={blocked}
          disabled={sessionActive || (cloud && !current.credentialId)}
          onChange={(model) => setPick({ ...current, model })}
          placeholder={t('architect.model.pick')}
          noModelsLabel={t('network.inspector.llm.noModels')}
          customValueLabel={local ? undefined : (name) => t('network.inspector.llm.useModel', { name })}
          restrictToOptions={local}
        />
      </div>
      <div className="flex items-center gap-2 pb-0.5">
        {sessionActive ? (
          <Button type="button" size="sm" variant="outline" onClick={onStop} disabled={busy}>
            <Square className="size-4" aria-hidden />
            {t('architect.session.stop')}
          </Button>
        ) : (
          <Button type="button" size="sm" onClick={() => onStart(current)} disabled={!canStart}>
            <Play className="size-4" aria-hidden />
            {t('architect.session.start')}
          </Button>
        )}
        {active && sessionActive ? (
          <Badge variant={active.slow ? 'warning' : 'default'}>
            {active.slow ? t('architect.session.slow') : t('architect.session.running')}
          </Badge>
        ) : null}
      </div>
      {!sessionActive && check ? (
        <div className="flex w-full flex-wrap gap-x-3 gap-y-1 text-xs">
          {check.model.reasons.map((key) => (
            <span key={key} className="text-destructive">
              {t(key)}
            </span>
          ))}
          {check.model.warnings.map((key) => (
            <span key={key} className="text-muted-foreground">
              {t(key)}
            </span>
          ))}
          {check.gpu ? (
            <span className={check.gpu.fits ? 'text-muted-foreground' : 'text-destructive'}>
              {t('architect.gpu.line', {
                need: formatBytes(check.gpu.needBytes, i18n.language),
                free: formatBytes(check.gpu.freeVramBytes, i18n.language),
              })}
            </span>
          ) : null}
          {cloud ? <span className="text-muted-foreground">{t('architect.cloud.notice')}</span> : null}
        </div>
      ) : null}
    </div>
  );
}
