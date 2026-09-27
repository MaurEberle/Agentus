import { useTranslation } from 'react-i18next';
import { BrandMark } from '@/components/BrandMark';

export function ModuleLoading() {
  const { t } = useTranslation();
  return (
    <div
      className="flex min-h-[50vh] flex-1 flex-col items-center justify-center gap-4 py-16"
      role="status"
      aria-label={t('app.loading')}
    >
      <BrandMark spinning className="size-24" alt="" />
      <p className="text-sm text-muted-foreground">{t('app.loading')}</p>
    </div>
  );
}
