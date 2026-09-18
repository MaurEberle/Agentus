import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { NetworkListItem } from '@/modules/dashboard/model';
import { validationBadgeVariant } from '@/modules/dashboard/model';
import { formatStamp } from '@/modules/networks/model/format';

export function DetailPanel({
  items,
  onOpen,
}: {
  items: NetworkListItem[];
  onOpen: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  if (items.length === 0) {
    return <p className="p-3 text-sm text-muted-foreground">{t('networks.detail.none')}</p>;
  }
  if (items.length > 1) {
    return <p className="p-3 text-sm text-muted-foreground">{t('networks.detail.multi', { count: items.length })}</p>;
  }
  const item = items[0];
  return (
    <div className="space-y-3 p-3">
      <div>
        <h2 className="text-sm font-semibold">{item.name}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{item.description || t('networks.detail.noDescription')}</p>
      </div>
      <div className="flex flex-wrap gap-1">
        <Badge variant={validationBadgeVariant(item.validationStatus)}>
          {t(`networks.badge.${item.validationStatus}`)}
        </Badge>
        {item.credentialMissing ? <Badge variant="destructive">{t('networks.badge.credentialMissing')}</Badge> : null}
        {item.isActive ? <Badge>{t('networks.badge.active')}</Badge> : null}
        {item.isRunning ? <Badge variant="warning">{t('networks.badge.running')}</Badge> : null}
        {(item.tags ?? []).map((tag) => (
          <Badge key={tag} variant="outline">
            {tag}
          </Badge>
        ))}
      </div>
      <dl className="grid gap-1 text-sm">
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">{t('networks.list.graph')}</dt>
          <dd>{t('networks.list.counts', { nodes: item.nodeCount, edges: item.edgeCount })}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">{t('networks.list.updated')}</dt>
          <dd>{formatStamp(item.updatedAt, i18n.language)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">{t('networks.list.lastUsed')}</dt>
          <dd>{formatStamp(item.lastUsedAt, i18n.language)}</dd>
        </div>
      </dl>
      {item.lastRunId ? (
        <Button asChild size="sm" variant="link" className="h-auto px-0">
          <Link to={`/history/${item.lastRunId}`}>{t('networks.detail.lastRun')}</Link>
        </Button>
      ) : null}
      <Button type="button" size="sm" onClick={() => onOpen(item.id)}>
        {t('networks.ribbon.open')}
      </Button>
    </div>
  );
}
