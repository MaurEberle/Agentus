import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { formatRelative } from '@/lib/relativeTime';
import { validationBadgeVariant, type NetworkListItem } from '@/modules/dashboard/model';
import { useAppStore } from '@/store';

export function ActiveNetworkCard({
  loading,
  item,
}: {
  loading: boolean;
  item?: NetworkListItem;
}) {
  const { t, i18n } = useTranslation();
  const activeNetworkId = useAppStore((state) => state.activeNetworkId);
  const network = item;
  const errors = item?.validationErrors ?? [];

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-36" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('dashboard.active.title')}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!activeNetworkId || !network ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">{t('dashboard.active.empty')}</p>
            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm">
                <Link to="/network">{t('dashboard.active.create')}</Link>
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link to="/networks">{t('dashboard.active.library')}</Link>
              </Button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 space-y-1">
                <p className="truncate font-medium">{network.name}</p>
                {network.description ? (
                  <p className="truncate text-sm text-muted-foreground">{network.description}</p>
                ) : null}
              </div>
              <Badge variant={validationBadgeVariant(network.validationStatus)}>
                {t(`dashboard.validationStatus.${network.validationStatus}`)}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              {t('dashboard.active.stats', { nodes: network.nodeCount, edges: network.edgeCount })}
            </p>
            <p className="text-xs text-muted-foreground">
              {t('dashboard.active.updated', {
                time: formatRelative(Date.parse(network.updatedAt), i18n.language),
              })}
            </p>
            {network.validationStatus === 'invalid' && errors.length > 0 ? (
              <ul className="list-disc space-y-1 pl-4 text-sm text-destructive">
                {errors.slice(0, 3).map((error) => (
                  <li key={`${error.nodeId ?? 'net'}-${error.messageKey}`}>{t(error.messageKey)}</li>
                ))}
              </ul>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm">
                <Link to={`/network/${network.id}`}>{t('dashboard.active.edit')}</Link>
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link to="/networks">{t('dashboard.active.library')}</Link>
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
