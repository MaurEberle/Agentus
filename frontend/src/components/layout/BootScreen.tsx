import { useTranslation } from 'react-i18next';
import { BrandMark } from '@/components/BrandMark';

export function BootScreen() {
  const { t } = useTranslation();
  return (
    <div className="flex h-svh min-h-0 flex-col items-center justify-center gap-5 bg-background text-foreground">
      <BrandMark spinning className="size-24" alt="" />
      <p className="text-sm text-muted-foreground" role="status">
        {t('app.loading')}
      </p>
    </div>
  );
}
