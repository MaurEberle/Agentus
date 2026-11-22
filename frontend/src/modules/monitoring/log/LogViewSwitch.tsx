import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { LOG_VIEWS, type LogView } from '@/modules/monitoring/model/logView';

/** U3: "Important", "All" and "Debug" instead of a minimum log level. */
export function LogViewSwitch({ value, onChange }: { value: LogView; onChange: (view: LogView) => void }) {
  const { t } = useTranslation();
  return (
    <div className="grid gap-1.5">
      {/* Same label and height as the other fields of the log toolbars. */}
      <p className="text-xs font-medium leading-none">{t('runLog.views.label')}</p>
      <div
        role="radiogroup"
        aria-label={t('runLog.views.label')}
        className="inline-flex h-8 items-stretch rounded-md border border-input p-0.5 shadow-sm"
      >
        {LOG_VIEWS.map((view) => (
          <button
            key={view}
            type="button"
            role="radio"
            aria-checked={value === view}
            title={t(`runLog.views.${view}Hint`)}
            onClick={() => onChange(view)}
            className={cn(
              'flex items-center rounded px-2.5 text-sm transition-colors',
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
