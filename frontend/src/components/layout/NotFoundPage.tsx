import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex max-w-lg flex-col items-start gap-4 p-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t('notFound.title')}</h1>
      <p className="text-sm text-muted-foreground">{t('notFound.body')}</p>
      <Button asChild>
        <Link to="/dashboard">{t('notFound.back')}</Link>
      </Button>
    </div>
  );
}
