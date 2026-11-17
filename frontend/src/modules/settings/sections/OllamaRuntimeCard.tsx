import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ApiError } from '@/api/client';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { notify } from '@/lib/notifications';
import { ollamaMessageKey } from '@/lib/ollamaRuntime';
import {
  applyOllamaUpdate,
  checkOllamaRuntime,
  patchSettings,
  restartApp,
  useOllamaRuntimeQuery,
  useSettingsQuery,
} from '@/modules/settings/api';
import type { OllamaRuntimeMode, OllamaRuntimeState } from '@/modules/settings/model';

const STATE_VARIANT: Record<OllamaRuntimeState, 'default' | 'secondary' | 'destructive'> = {
  running: 'default',
  preparing: 'secondary',
  starting: 'secondary',
  disabled: 'secondary',
  stopped: 'secondary',
  unavailable: 'secondary',
  failed: 'destructive',
};

function errorKey(error: unknown): string {
  const key = error instanceof ApiError ? error.messageKey : undefined;
  return ollamaMessageKey(key) ?? 'settings.notify.saveError';
}

/** Own Ollama copy: mode, status, update hint and restart. */
export function OllamaRuntimeCard() {
  const { t, i18n } = useTranslation();
  const { data: settings } = useSettingsQuery();
  const { data: status, refetch } = useOllamaRuntimeQuery();
  const [savingMode, setSavingMode] = useState(false);
  const [checking, setChecking] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [restarting, setRestarting] = useState(false);

  const configured: OllamaRuntimeMode = settings?.ollamaRuntime ?? status?.configuredMode ?? 'own';
  const own = status?.mode === 'own';
  const update = own ? status?.updateVersion : null;
  const blocked = Boolean(status?.runBusy || status?.downloadRunning);
  const messageKey = own ? ollamaMessageKey(status?.messageKey) : null;

  async function changeMode(next: string) {
    if (next !== 'own' && next !== 'external') return;
    setSavingMode(true);
    try {
      await patchSettings({ ollamaRuntime: next });
      await refetch();
    } catch {
      notify({ titleKey: 'settings.notify.saveError', variant: 'error' });
    } finally {
      setSavingMode(false);
    }
  }

  async function check() {
    setChecking(true);
    try {
      const next = await checkOllamaRuntime();
      if (!next.updateVersion) {
        notify({ titleKey: 'settings.runtime.own.checkNone', variant: 'success', persist: false });
      }
    } catch (error) {
      notify({ titleKey: errorKey(error), variant: 'error' });
    } finally {
      setChecking(false);
    }
  }

  async function takeOver() {
    setUpdating(true);
    try {
      const result = await applyOllamaUpdate();
      setConfirmOpen(false);
      if (result.restart) {
        setRestarting(true);
      } else {
        notify({
          titleKey: 'settings.runtime.own.staged',
          values: { version: result.version },
          variant: 'success',
        });
      }
    } catch (error) {
      setConfirmOpen(false);
      notify({ titleKey: errorKey(error), values: { version: update ?? '' }, variant: 'error' });
      void refetch();
    } finally {
      setUpdating(false);
    }
  }

  async function restart() {
    try {
      const result = await restartApp();
      if (result.restart) setRestarting(true);
      else notify({ titleKey: 'settings.runtime.own.restartManual', variant: 'info' });
    } catch (error) {
      notify({ titleKey: errorKey(error), variant: 'error' });
    }
  }

  const checkedAt = status?.checkedAt ? new Date(status.checkedAt) : null;

  return (
    <section className="space-y-4 rounded-lg border p-4">
      <div className="space-y-1">
        <h3 className="text-sm font-medium">{t('settings.runtime.own.title')}</h3>
        <p className="text-sm text-muted-foreground">{t('settings.runtime.own.lead')}</p>
      </div>

      <RadioGroup
        value={configured}
        onValueChange={(value) => void changeMode(value)}
        className="grid gap-3"
        disabled={savingMode || restarting}
        aria-label={t('settings.runtime.own.modeLabel')}
      >
        {(
          [
            ['own', 'settings.runtime.own.modeOwn', 'settings.runtime.own.modeOwnHint'],
            ['external', 'settings.runtime.own.modeExternal', 'settings.runtime.own.modeExternalHint'],
          ] as const
        ).map(([value, label, hint]) => (
          <label key={value} className="flex items-start gap-2 text-sm">
            <RadioGroupItem value={value} id={`ollama-mode-${value}`} className="mt-0.5" />
            <span>
              <span className="font-medium">{t(label)}</span>
              <span className="block text-xs text-muted-foreground">{t(hint)}</span>
            </span>
          </label>
        ))}
      </RadioGroup>

      {status ? (
        <dl className="grid gap-1 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <dt className="sr-only">{t('settings.runtime.own.stateLabel')}</dt>
            <dd>
              <Badge variant={STATE_VARIANT[status.state]}>{t(`settings.runtime.own.state.${status.state}`)}</Badge>
            </dd>
            {own && status.version ? (
              <dd className="text-muted-foreground">
                {t('settings.runtime.own.version', { version: status.version })}
                {status.port ? ` · ${t('settings.runtime.own.port', { port: String(status.port) })}` : ''}
              </dd>
            ) : null}
          </div>
          {own ? (
            <div className="text-muted-foreground">
              <dt className="sr-only">{t('settings.runtime.own.installedLabel')}</dt>
              <dd>
                {status.installedVersion
                  ? t('settings.runtime.own.installed', { version: status.installedVersion })
                  : t('settings.runtime.own.installedNone')}
                {checkedAt
                  ? ` · ${t('settings.runtime.own.checkedAt', {
                      time: checkedAt.toLocaleString(i18n.language),
                    })}`
                  : ''}
              </dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      {restarting ? (
        <Alert>
          <AlertTitle>{t('settings.runtime.own.restarting')}</AlertTitle>
        </Alert>
      ) : null}

      {!restarting && update ? (
        <Alert>
          <AlertTitle>{t('settings.runtime.own.updateTitle', { version: update })}</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>{t('settings.runtime.own.updateDesc', { current: status?.version ?? '' })}</p>
            {status?.runBusy ? <p>{t('settings.runtime.own.messages.busy')}</p> : null}
            {status?.downloadRunning ? <p>{t('settings.runtime.own.messages.downloadRunning')}</p> : null}
            <Button type="button" size="sm" disabled={blocked} onClick={() => setConfirmOpen(true)}>
              {t('settings.runtime.own.updateButton')}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {!restarting && status?.restartRequired ? (
        <Alert>
          <AlertTitle>{t('settings.runtime.own.restartTitle')}</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>
              {status.stagedVersion
                ? t('settings.runtime.own.staged', { version: status.stagedVersion })
                : t('settings.runtime.own.restartModeDesc')}
            </p>
            <Button type="button" size="sm" variant="outline" disabled={status.runBusy} onClick={() => void restart()}>
              {t('settings.runtime.own.restartButton')}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {messageKey ? (
        <Alert variant={status?.state === 'failed' ? 'destructive' : 'default'}>
          <AlertDescription>{t(messageKey, status?.messageParams ?? {})}</AlertDescription>
        </Alert>
      ) : null}

      {own ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => void check()} loading={checking} disabled={checking || restarting}>
            {t('settings.runtime.own.check')}
          </Button>
          {status?.logPath ? (
            <span className="break-all text-xs text-muted-foreground">
              {t('settings.runtime.own.logPath', { path: status.logPath })}
            </span>
          ) : null}
        </div>
      ) : null}

      <AlertDialog open={confirmOpen} onOpenChange={(open) => !updating && setConfirmOpen(open)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('settings.runtime.own.confirmTitle', { version: update ?? '' })}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('settings.runtime.own.confirmDesc', { current: status?.version ?? '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button type="button" variant="outline" disabled={updating} onClick={() => setConfirmOpen(false)}>
              {t('settings.common.cancel')}
            </Button>
            <Button type="button" loading={updating} disabled={updating} onClick={() => void takeOver()}>
              {t('settings.runtime.own.confirmOk')}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
