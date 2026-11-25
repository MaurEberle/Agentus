import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BRIEF_FIELDS, patchSession, type Brief, type BriefField } from '@/modules/architect/api';

/** E-9: the brief the architect fills in conversation; every field can be edited directly. */
export function BriefPanel({ sessionId, brief }: { sessionId: string | null; brief: Brief }) {
  const { t } = useTranslation();
  const [values, setValues] = useState<Brief>(brief);
  useEffect(() => setValues(brief), [brief]);

  function save(field: BriefField) {
    if (!sessionId || (values[field] ?? '') === (brief[field] ?? '')) return;
    void patchSession(sessionId, { brief: { ...brief, [field]: values[field] ?? '' } });
  }

  const empty = BRIEF_FIELDS.every((field) => !(brief[field] ?? '').trim());
  return (
    <section className="grid gap-2 p-3">
      <h2 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{t('architect.brief.title')}</h2>
      {empty ? <p className="text-xs text-muted-foreground">{t('architect.brief.empty')}</p> : null}
      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-baseline gap-x-3 gap-y-1 text-sm">
        {BRIEF_FIELDS.map((field) => (
          <div key={field} className="contents">
            <dt className="text-muted-foreground">{t(`architect.brief.${field}`)}</dt>
            <dd className="min-w-0">
              <input
                value={values[field] ?? ''}
                disabled={!sessionId}
                placeholder="—"
                aria-label={t(`architect.brief.${field}`)}
                onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value }))}
                onBlur={() => save(field)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') (event.target as HTMLInputElement).blur();
                }}
                className="w-full rounded-sm border border-transparent bg-transparent px-1 py-0.5 hover:border-input focus:border-input focus:outline-none"
              />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
