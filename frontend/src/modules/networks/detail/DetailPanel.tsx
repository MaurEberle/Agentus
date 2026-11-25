import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, FolderOpen } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatRelative } from '@/lib/relativeTime';
import { validationTextKey } from '@/lib/validationText';
import type { NetworkListItem } from '@/modules/dashboard/model';
import { validationBadgeVariant } from '@/modules/dashboard/model';
import { formatStamp } from '@/modules/networks/model/format';
import { KindBadge } from '@/modules/networks/list/KindBadge';
import { ReadonlyGraph } from '@/modules/networks/detail/ReadonlyGraph';

const SHOWN_ERRORS = 3;

/** One label/value pair; the labels are the words the filter bar uses. */
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="contents">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

function Stamp({ iso, locale }: { iso: string; locale: string }) {
  return (
    <>
      <span className="tabular-nums">{formatStamp(iso, locale)}</span>
      <span className="text-muted-foreground">{formatRelative(Date.parse(iso), locale)}</span>
    </>
  );
}

export function DetailPanel({
  items,
  onOpen,
  layoutWidth = 0,
}: {
  items: NetworkListItem[];
  onOpen: (id: string) => void;
  layoutWidth?: number;
}) {
  const { t, i18n } = useTranslation();
  if (items.length === 0) {
    return (
      <p className="flex h-full min-h-0 flex-1 items-center justify-center p-3 text-center text-sm text-muted-foreground">
        {t('networks.detail.none')}
      </p>
    );
  }
  if (items.length > 1) {
    return (
      <p className="flex h-full min-h-0 flex-1 items-center justify-center p-3 text-center text-sm text-muted-foreground">
        {t('networks.detail.multi', { count: items.length })}
      </p>
    );
  }
  const item = items[0];
  const locale = i18n.language;
  const tags = item.tags ?? [];
  const errors = item.validationStatus === 'invalid' ? (item.validationErrors ?? []) : [];
  return (
    <div className="flex min-h-0 w-full flex-1 flex-col">
      <div className="space-y-4 p-3">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="break-words text-base font-semibold">{item.name}</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">{item.description || t('networks.detail.noDescription')}</p>
          </div>
          <Button type="button" size="sm" className="shrink-0" onClick={() => onOpen(item.id)}>
            <FolderOpen className="size-4" aria-hidden />
            {t('networks.ribbon.open')}
          </Button>
        </div>
        <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-baseline gap-x-6 gap-y-2.5 text-sm">
          <Fact label={t('networks.list.kind')}>
            <KindBadge kind={item.kind} />
          </Fact>
          <Fact label={t('networks.list.status')}>
            <div className="flex flex-wrap gap-1">
              <Badge variant={validationBadgeVariant(item.validationStatus)}>
                {t(`networks.badge.${item.validationStatus}`)}
              </Badge>
              {item.credentialMissing ? <Badge variant="destructive">{t('networks.badge.credentialMissing')}</Badge> : null}
              {item.isActive ? <Badge>{t('networks.badge.active')}</Badge> : null}
              {item.isRunning ? <Badge variant="warning">{t('networks.badge.running')}</Badge> : null}
            </div>
            {errors.length > 0 ? (
              <ul className="mt-1.5 space-y-0.5 text-xs text-destructive">
                {errors.slice(0, SHOWN_ERRORS).map((error) => (
                  <li key={`${error.nodeId ?? 'net'}-${error.messageKey}`}>{t(validationTextKey(error.messageKey))}</li>
                ))}
                {errors.length > SHOWN_ERRORS ? (
                  <li>{t('networks.detail.moreErrors', { count: errors.length - SHOWN_ERRORS })}</li>
                ) : null}
              </ul>
            ) : null}
          </Fact>
          <Fact label={t('networks.list.tags')}>
            {tags.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {tags.map((tag) => (
                  <Badge key={tag} variant="outline" className="max-w-full break-all">
                    {tag}
                  </Badge>
                ))}
              </div>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </Fact>
          <Fact label={t('networks.list.updated')}>
            <span className="flex flex-wrap items-baseline gap-x-2">
              <Stamp iso={item.updatedAt} locale={locale} />
              {item.version ? (
                <Link
                  to={`/network/${item.id}?versions=1`}
                  className="inline-flex items-center gap-0.5 text-primary underline-offset-4 hover:underline"
                >
                  {t('network.versions.version', { version: item.version })}
                  <ArrowUpRight className="size-3.5" aria-hidden />
                </Link>
              ) : null}
            </span>
          </Fact>
          <Fact label={t('networks.list.lastUsed')}>
            <span className="flex flex-wrap items-baseline gap-x-2">
              {item.lastUsedAt ? (
                <Stamp iso={item.lastUsedAt} locale={locale} />
              ) : (
                <span className="text-muted-foreground">{t('networks.detail.neverUsed')}</span>
              )}
              {item.lastRunId ? (
                <Link
                  to={`/history/${item.lastRunId}`}
                  className="inline-flex items-center gap-0.5 text-primary underline-offset-4 hover:underline"
                >
                  {t('networks.detail.lastRun')}
                  <ArrowUpRight className="size-3.5" aria-hidden />
                </Link>
              ) : null}
            </span>
          </Fact>
        </dl>
      </div>
      <div className="min-h-64 min-w-0 flex-1 overflow-hidden border-t">
        <ReadonlyGraph id={item.id} layoutWidth={layoutWidth} />
      </div>
    </div>
  );
}
