import { Link } from 'react-router-dom';
import { FolderInput, GitBranch, Server } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { moduleCardBodyClass, moduleCardClass } from '@/modules/moduleCard';

export function QuickLinks() {
  const { t } = useTranslation();

  return (
    <Card className={moduleCardClass}>
      <CardHeader>
        <CardTitle>{t('dashboard.quick.title')}</CardTitle>
      </CardHeader>
      <CardContent className={`${moduleCardBodyClass} flex flex-wrap gap-2`}>
        <Button asChild size="sm">
          <Link to="/network">
            <GitBranch />
            {t('dashboard.quick.create')}
          </Link>
        </Button>
        <Button asChild size="sm" variant="outline">
          <Link to="/networks">
            <FolderInput />
            {t('dashboard.quick.import')}
          </Link>
        </Button>
        <Button asChild size="sm" variant="outline">
          <Link to="/settings#runtime">
            <Server />
            {t('dashboard.quick.runtime')}
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
