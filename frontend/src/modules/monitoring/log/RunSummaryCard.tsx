import { CheckCircle2, CircleSlash, OctagonAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { formatRunLogMessage } from '@/modules/monitoring/model/logMessage';
import { formatMs, limitLabel, readSummary } from '@/modules/monitoring/model/logView';
import type { LogEvent } from '@/modules/monitoring/model/types';

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className="truncate text-sm font-medium tabular-nums" title={hint}>
        {value}
      </p>
    </div>
  );
}

/** U8: what the run did, from its run.summary line. */
export function RunSummaryCard({ event, locale }: { event: LogEvent; locale: string }) {
  const { t } = useTranslation();
  const summary = readSummary(event);
  const number = (value: number) => new Intl.NumberFormat(locale).format(value);
  const outcome = summary.outcome;
  const Icon = outcome === 'succeeded' ? CheckCircle2 : outcome === 'cancelled' ? CircleSlash : OctagonAlert;
  const limits = Object.entries(summary.limits);
  const agents = summary.agents.map((item) => {
    const base =
      item.failed > 0
        ? t('runLog.summary.agentFailed', { name: item.name, count: item.calls, failed: item.failed })
        : t('runLog.summary.agent', { name: item.name, count: item.calls });
    if (item.contextShare === null) return base;
    const share = new Intl.NumberFormat(locale, { maximumFractionDigits: item.contextShare < 10 ? 1 : 0 }).format(
      item.contextShare,
    );
    return `${base} (${t('runLog.summary.contextShare', { share })})`;
  });
  return (
    <section
      aria-label={t('runLog.summary.title')}
      className={cn(
        'space-y-2 rounded-md border px-3 py-2',
        outcome === 'succeeded' && 'border-primary/40',
        outcome === 'failed' && 'border-destructive/50 bg-destructive/5',
        outcome === 'cancelled' && 'border-warning/60',
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Icon
          className={cn(
            'size-4',
            outcome === 'succeeded' && 'text-primary',
            outcome === 'failed' && 'text-destructive',
            outcome === 'cancelled' && 'text-warning',
          )}
          aria-hidden
        />
        <span className="text-sm font-semibold">
          {t(`runLog.summary.outcomes.${outcome}`, { defaultValue: outcome })}
        </span>
        <span className="text-sm text-muted-foreground">· {formatMs(summary.durationMs, locale)}</span>
        {summary.error ? (
          <span className="min-w-0 truncate text-sm text-destructive" title={summary.error}>
            · {formatRunLogMessage(summary.error, t)}
          </span>
        ) : null}
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
        <Stat label={t('runLog.summary.agentCalls')} value={number(summary.agentCalls)} hint={agents.join('\n')} />
        <Stat
          label={t('runLog.summary.llmCalls')}
          value={number(summary.llmCalls)}
          hint={t('runLog.summary.tokens', { tokensIn: number(summary.tokensIn), tokensOut: number(summary.tokensOut) })}
        />
        <Stat
          label={t('runLog.summary.toolCalls')}
          value={`${number(summary.toolCalls)}${summary.toolsFailed ? ` · ✗ ${number(summary.toolsFailed)}` : ''}`}
        />
        <Stat label={t('runLog.summary.files')} value={number(summary.filesCount)} hint={summary.files.join('\n')} />
      </div>
      {agents.length ? <p className="text-xs text-muted-foreground">{agents.join(' · ')}</p> : null}
      {limits.length ? (
        <p className="text-xs">
          <span className="rounded bg-warning/30 px-1">{t('runLog.summary.limits')}</span>{' '}
          {limits.map(([key, count]) => `${limitLabel(key, t)} ×${count}`).join(' · ')}
        </p>
      ) : null}
      {summary.files.length ? (
        <details className="text-xs">
          <summary className="cursor-pointer text-muted-foreground">
            {t('runLog.summary.fileList', { count: summary.filesCount })}
          </summary>
          <ul className="mt-1 max-h-32 overflow-auto font-log">
            {summary.files.map((file) => (
              <li key={file} className="truncate">
                {file}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
