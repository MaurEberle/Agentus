import { useTranslation } from 'react-i18next';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CONTEXT_STEPS, contextLabel } from '@/modules/models/hubFit';

/** Minimum context window; models whose GGUF does not state one are left out while it is set. */
export function HubContextFilter({ value, onChange }: { value: number; onChange: (next: number) => void }) {
  const { t } = useTranslation();
  return (
    <Select value={String(value)} onValueChange={(next) => onChange(Number(next))}>
      <SelectTrigger className="h-8 w-fit shrink-0 gap-1.5 [&>span]:flex-none" aria-label={t('models.hub.context')}>
        <SelectValue>
          <span className="flex items-center gap-1.5">
            {t('models.hub.context')}
            {value ? (
              <span className="inline-flex h-5 items-center rounded-full bg-primary px-1.5 text-[11px] font-medium text-primary-foreground">
                ≥ {contextLabel(value)}
              </span>
            ) : null}
          </span>
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="0">{t('models.hub.contextAny')}</SelectItem>
        {CONTEXT_STEPS.map((step) => (
          <SelectItem key={step} value={String(step)}>
            ≥ {contextLabel(step)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
