import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatBytes, formatPercent, meterTone } from '@/modules/monitoring/model/format';
import type { ResourceSnapshot } from '@/modules/monitoring/model/types';
import { moduleCardBodyClass, moduleCardClass } from '@/modules/moduleCard';

function Meter({
  label,
  percent,
  detail,
  alarm,
  locale,
}: {
  label: string;
  percent: number;
  detail?: string;
  alarm: boolean;
  locale: string;
}) {
  const tone = meterTone(percent, alarm);
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-medium">{label}</span>
        <span className="tabular-nums text-muted-foreground">
          {formatPercent(percent, locale)}
          {detail ? ` · ${detail}` : ''}
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-muted"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percent)}
        aria-label={label}
      >
        <div
          className={cn(
            'h-full rounded-full',
            tone === 'off' && 'bg-muted-foreground/30',
            tone === 'normal' && 'bg-primary',
            tone === 'warn' && 'bg-warning',
            tone === 'hot' && 'bg-destructive',
          )}
          style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
        />
      </div>
    </div>
  );
}

export function ResourcesPanel({
  resources,
  dimmed,
}: {
  resources: ResourceSnapshot | null;
  dimmed?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const [coresOpen, setCoresOpen] = useState(false);
  const locale = i18n.language;
  const gpus = resources?.gpus ?? [];
  const ramPct =
    resources && resources.ramTotalBytes > 0
      ? (resources.ramUsedBytes / resources.ramTotalBytes) * 100
      : 0;

  return (
    <Card className={cn(moduleCardClass, dimmed && 'opacity-60')}>
      <CardHeader className="pb-2">
        <CardTitle>{t('monitoring.resources.title')}</CardTitle>
        <CardDescription>{t('monitoring.resources.hostHint')}</CardDescription>
      </CardHeader>
      <CardContent className={cn(moduleCardBodyClass, 'grid gap-4 sm:grid-cols-3')}>
        <div className="space-y-2">
          <Meter
            label={t('monitoring.resources.cpu')}
            percent={resources?.cpuPercent ?? 0}
            alarm={Boolean(resources)}
            locale={locale}
          />
          {resources?.cpuPerCore && resources.cpuPerCore.length > 0 ? (
            <div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => setCoresOpen((open) => !open)}
              >
                {t('monitoring.resources.cpuCores')}
              </Button>
              {coresOpen ? (
                <ul className="mt-1 max-h-40 space-y-1 overflow-y-auto">
                  {resources.cpuPerCore.map((value, index) => (
                    <li key={index}>
                      <Meter label={`${index + 1}`} percent={value} alarm locale={locale} />
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </div>
        <Meter
          label={t('monitoring.resources.ram')}
          percent={ramPct}
          detail={
            resources
              ? t('monitoring.resources.usedOf', {
                  used: formatBytes(resources.ramUsedBytes, locale),
                  total: formatBytes(resources.ramTotalBytes, locale),
                })
              : undefined
          }
          alarm={Boolean(resources)}
          locale={locale}
        />
        {gpus.length === 0 ? (
          <div className="rounded-md border border-dashed p-3">
            <p className="text-sm font-medium">{t('monitoring.resources.noGpu')}</p>
            <p className="mt-1 text-xs text-muted-foreground">{t('monitoring.resources.noGpuHint')}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {gpus.map((gpu) => {
              const vramPct = gpu.vramTotalBytes > 0 ? (gpu.vramUsedBytes / gpu.vramTotalBytes) * 100 : 0;
              const name = gpu.name ? `${gpu.index}: ${gpu.name}` : `${t('monitoring.resources.gpu')} ${gpu.index}`;
              return (
                <div key={gpu.index} className="space-y-2">
                  <Meter label={name} percent={gpu.utilPercent} alarm locale={locale} />
                  <Meter
                    label={t('monitoring.resources.vram')}
                    percent={vramPct}
                    detail={t('monitoring.resources.usedOf', {
                      used: formatBytes(gpu.vramUsedBytes, locale),
                      total: formatBytes(gpu.vramTotalBytes, locale),
                    })}
                    alarm
                    locale={locale}
                  />
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
