import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { LOG_VIEWS, type LogView } from '@/modules/monitoring/model/logView';

/** U3: "Important", "All" and "Debug" instead of a minimum log level. */
export function LogViewSwitch({ value, onChange }: { value: LogView; onChange: (view: LogView) => void }) {
  const { t } = useTranslation();
  return (
    <div>
      <p className="text-xs font-medium">{t('runLog.views.label')}</p>
      <div role="radiogroup" aria-label={t('runLog.views.label')} className="mt-1 inline-flex rounded-md border p-0.5">
        {LOG_VIEWS.map((view) => (
          <button
            key={view}
            type="button"
            role="radio"
            aria-checked={value === view}
            title={t(`runLog.views.${view}Hint`)}
            onClick={() => onChange(view)}
            className={cn(
              'rounded px-2.5 py-1 text-xs transition-colors',
              value === view ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted',
            )}
          >
            {t(`runLog.views.${view}`)}
          </button>
        ))}
      </div>
    </div>
  );
}
