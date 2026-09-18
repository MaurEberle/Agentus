import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { formatRelative } from '@/lib/relativeTime';
import { recentNetworks, type NetworkListItem } from '@/modules/dashboard/model';

export function RecentNetworksCard({
  loading,
  items,
}: {
  loading: boolean;
  items: NetworkListItem[];
}) {
  const { t, i18n } = useTranslation();
  const recent = recentNetworks(items);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-40" />
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('dashboard.recent.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        {recent.length === 0 ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">{t('dashboard.recent.empty')}</p>
            <Button asChild size="sm">
              <Link to="/network">{t('dashboard.recent.create')}</Link>
            </Button>
          </div>
        ) : (
          <ul className="space-y-1">
            {recent.map((network) => (
              <li key={network.id}>
                <Link
                  to={`/network/${network.id}`}
                  className="flex items-center justify-between gap-2 rounded-md px-2 py-2 text-sm hover:bg-accent"
                >
                  <span className="truncate font-medium">{network.name}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatRelative(Date.parse(network.updatedAt), i18n.language)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
