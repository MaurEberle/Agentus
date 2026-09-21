import { useTranslation } from 'react-i18next';
import { BrandMark } from '@/components/BrandMark';
import { Spinner } from '@/components/ui/spinner';

export function BootScreen() {
  const { t } = useTranslation();
  return (
    <div className="flex h-svh min-h-0 flex-col items-center justify-center gap-5 bg-background text-foreground">
      <BrandMark className="size-16" alt="" />
      <Spinner size="lg" className="text-primary" label={t('app.loading')} />
      <p className="text-sm text-muted-foreground">{t('app.loading')}</p>
    </div>
  );
}
