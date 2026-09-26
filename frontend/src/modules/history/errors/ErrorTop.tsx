import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { formatInt } from '@/modules/history/model/format';
import { formatRunLogMessage } from '@/modules/monitoring/model/logMessage';
import { moduleCardBodyClass, moduleCardClass } from '@/modules/moduleCard';
import type { ErrorTopRow } from '@/modules/history/model/types';

export function ErrorTop({
  rows,
  onPick,
}: {
  rows: ErrorTopRow[];
  onPick: (row: ErrorTopRow) => void;
}) {
  const { t, i18n } = useTranslation();
  return (
    <Card className={`${moduleCardClass} min-w-0`}>
      <CardHeader className="shrink-0 pb-2">
        <CardTitle>{t('history.errors.title')}</CardTitle>
      </CardHeader>
      <CardContent className={moduleCardBodyClass}>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('history.errors.empty')}</p>
        ) : (
          <ul className="space-y-1">
            {rows.map((row) => (
              <li key={row.id}>
                <Button
                  type="button"
                  variant="ghost"
                  className="h-auto w-full justify-between px-2 py-1.5 text-left"
                  onClick={() => onPick(row)}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{formatRunLogMessage(row.message, t)}</span>
                    <span className="text-xs text-muted-foreground">
                      {t(`history.errorClass.${row.errorClass}`)}
                      {row.nodeName ? ` · ${row.nodeName}` : ''}
                    </span>
                  </span>
                  <span className="tabular-nums text-sm">{formatInt(row.count, i18n.language)}</span>
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
