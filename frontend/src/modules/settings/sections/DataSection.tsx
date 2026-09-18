import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { notify } from '@/lib/notifications';
import { patchSettings, pickDataDir, setDataDir, useSettingsQuery, useStoresQuery } from '@/modules/settings/api';
import { isForbiddenDataRoot, type HistoryRetentionDays } from '@/modules/settings/model';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';
import { useSettingsDraft } from '@/modules/settings/store';
import { useAppStore } from '@/store';

const RETENTION_OPTIONS: Array<{ value: string; days: HistoryRetentionDays }> = [
  { value: '30', days: 30 },
  { value: '90', days: 90 },
  { value: '365', days: 365 },
  { value: 'unlimited', days: null },
];

export function DataSection() {
  const { t } = useTranslation();
  const { data: settings } = useSettingsQuery();
  const { data: location } = useStoresQuery();
  const serviceStatus = useAppStore((state) => state.serviceStatus);
  const dataDraft = useSettingsDraft((state) => state.data);
  const setData = useSettingsDraft((state) => state.setData);
  const dirty = useSettingsDraft((state) => state.dataDirty(settings));
  const busy =
    serviceStatus === 'starting' || serviceStatus === 'running' || serviceStatus === 'stopping';
  const readOnly = Boolean(location?.readOnly) || location?.source === 'env' || location?.source === 'portable';
  const [pendingPath, setPendingPath] = useState<string | null>(null);
  const [copy, setCopy] = useState(false);
  const [saving, setSaving] = useState(false);

  async function chooseFolder() {
    if (busy || readOnly) return;
    const path = await pickDataDir();
    if (!path) return;
    if (isForbiddenDataRoot(path)) {
      notify({ titleKey: 'settings.data.invalidRoot', variant: 'error' });
      return;
    }
    setPendingPath(path);
  }

  async function confirmDir() {
    if (!pendingPath) return;
    try {
      await setDataDir({ path: pendingPath, copy });
      notify({ titleKey: 'settings.notify.dataDirOk', variant: 'success' });
      setPendingPath(null);
      setCopy(false);
    } catch {
      notify({ titleKey: 'settings.notify.saveError', variant: 'error' });
    }
  }

  async function saveRetention() {
    if (!dataDraft) return;
    setSaving(true);
    try {
      await patchSettings({ historyRetentionDays: dataDraft.historyRetentionDays });
      notify({ titleKey: 'settings.notify.saved', variant: 'success' });
    } catch {
      notify({ titleKey: 'settings.notify.saveError', variant: 'error' });
    } finally {
      setSaving(false);
    }
  }

  const pickButton = (
    <Button type="button" variant="outline" disabled={busy || readOnly} onClick={() => void chooseFolder()}>
      {t('settings.data.pick')}
    </Button>
  );

  return (
    <div className="max-w-2xl space-y-6">
      <SectionHeader title={t('settings.nav.data')} description={t('settings.data.lead')} />
      <div className="space-y-2">
        <Label>{t('settings.data.dir')}</Label>
        <p className="break-all rounded-md border bg-muted/40 px-3 py-2 font-mono text-xs">
          {location?.dataDir ?? '—'}
        </p>
        {location?.source && location.source !== 'config' && location.source !== 'default' ? (
          <Alert>
            <AlertDescription>{t(`settings.data.source.${location.source}`)}</AlertDescription>
          </Alert>
        ) : null}
        {busy ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span>{pickButton}</span>
            </TooltipTrigger>
            <TooltipContent>{t('settings.data.busy')}</TooltipContent>
          </Tooltip>
        ) : (
          pickButton
        )}
      </div>
      <div>
        <h2 className="mb-2 text-sm font-medium">{t('settings.data.stores')}</h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('settings.data.storeName')}</TableHead>
              <TableHead>{t('settings.data.fileName')}</TableHead>
              <TableHead>{t('settings.mcp.status')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(location?.stores ?? []).map((store) => (
              <TableRow key={store.id}>
                <TableCell>{t(`settings.data.store.${store.id}`)}</TableCell>
                <TableCell className="font-mono text-xs">{store.fileName}</TableCell>
                <TableCell>
                  <Badge variant={store.state === 'ok' ? 'default' : 'destructive'}>
                    {t(`settings.data.storeState.${store.state}`)}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">{t('settings.data.retentionLabel')}</legend>
        <RadioGroup
          value={
            dataDraft?.historyRetentionDays === null
              ? 'unlimited'
              : String(dataDraft?.historyRetentionDays ?? 90)
          }
          onValueChange={(value) => {
            const option = RETENTION_OPTIONS.find((item) => item.value === value);
            if (option) setData({ historyRetentionDays: option.days });
          }}
        >
          {RETENTION_OPTIONS.map((option) => (
            <label key={option.value} className="flex items-center gap-2 text-sm">
              <RadioGroupItem value={option.value} id={`ret-${option.value}`} />
              <span>{t(`settings.data.retention.${option.value}`)}</span>
            </label>
          ))}
        </RadioGroup>
        <Button type="button" onClick={() => void saveRetention()} disabled={!dirty || saving}>
          {t('settings.common.save')}
        </Button>
      </fieldset>

      <Dialog open={pendingPath !== null} onOpenChange={(open) => !open && setPendingPath(null)}>
        <DialogContent closeLabel={t('settings.common.close')}>
          <DialogHeader>
            <DialogTitle>{t('settings.data.confirmTitle')}</DialogTitle>
            <DialogDescription>{pendingPath}</DialogDescription>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">{t('settings.data.confirmBody')}</p>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={copy} onCheckedChange={(value) => setCopy(value === true)} />
            {t('settings.data.copy')}
          </label>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setPendingPath(null)}>
              {t('settings.common.cancel')}
            </Button>
            <Button type="button" onClick={() => void confirmDir()}>
              {t('settings.common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
