import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '@/api/client';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { formatDateTime } from '@/modules/monitoring/model/format';

type PreviousRun = {
  runId: string;
  startedAt: string;
  endedAt?: string | null;
  outcome: string;
  errorMessage?: string | null;
  request: string;
};

const NONE = 'none';

/**
 * Earlier run of this network to continue from. Shown while the run waits for its first
 * message; the orchestrator reads the chosen run before its first decision.
 */
export function PreviousRunPicker({
  runId,
  value,
  onChange,
}: {
  runId: string;
  value: string;
  onChange: (runId: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const query = useQuery({
    queryKey: ['run', 'previous', runId],
    queryFn: () => apiFetch<{ items: PreviousRun[] }>('/run/previous'),
    staleTime: 30_000,
  });
  const items = query.data?.items ?? [];
  if (items.length === 0) return null;
  const label = (item: PreviousRun) =>
    t('monitoring.chat.previous.option', {
      when: formatDateTime(item.startedAt, i18n.language),
      outcome: t(`history.outcome.${item.outcome}`, { defaultValue: item.outcome }),
      request: item.request || t('monitoring.chat.previous.noRequest'),
    });
  return (
    <div className="mb-2 space-y-1">
      <Label htmlFor="previous-run" className="text-xs">
        {t('monitoring.chat.previous.label')}
      </Label>
      <Select value={value || NONE} onValueChange={(next) => onChange(next === NONE ? '' : next)}>
        <SelectTrigger id="previous-run" className="h-8 text-xs">
          <SelectValue />
        </SelectTrigger>
        {/* As wide as the field; each line is cut at the right edge, the full text is in the tooltip. */}
        <SelectContent className="w-[var(--radix-select-trigger-width)]">
          <SelectItem value={NONE}>{t('monitoring.chat.previous.none')}</SelectItem>
          {items.map((item) => (
            <SelectItem key={item.runId} value={item.runId} className="[&>span:last-child]:min-w-0" title={label(item)}>
              <span className="block truncate">{label(item)}</span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {value ? <p className="text-xs text-muted-foreground">{t('monitoring.chat.previous.hint')}</p> : null}
    </div>
  );
}
