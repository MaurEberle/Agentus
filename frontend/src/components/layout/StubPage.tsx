import { useTranslation } from 'react-i18next';

export function StubPage({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation();
  return (
    <div className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t(titleKey)}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{t('stub.body')}</p>
    </div>
  );
}
