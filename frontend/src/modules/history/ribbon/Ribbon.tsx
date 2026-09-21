import { RefreshCw, Trash2, Download, Clock } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

export function HistoryRibbon({
  selectedCount,
  busy,
  onRefresh,
  onDelete,
  onExport,
  onPurge,
}: {
  selectedCount: number;
  busy: boolean;
  onRefresh: () => void;
  onDelete: () => void;
  onExport: () => void;
  onPurge: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button type="button" size="sm" variant="outline" onClick={onRefresh} disabled={busy} loading={busy}>
        <RefreshCw className="size-3.5" />
        {t('history.ribbon.refresh')}
      </Button>
      <Button type="button" size="sm" variant="outline" onClick={onDelete} disabled={busy || selectedCount === 0} loading={busy}>
        <Trash2 className="size-3.5" />
        {t('history.ribbon.delete')}
      </Button>
      <Button type="button" size="sm" variant="outline" onClick={onExport} disabled={busy || selectedCount === 0} loading={busy}>
        <Download className="size-3.5" />
        {t('history.ribbon.export')}
      </Button>
      <Button type="button" size="sm" variant="outline" onClick={onPurge} disabled={busy} loading={busy}>
        <Clock className="size-3.5" />
        {t('history.ribbon.purge')}
      </Button>
    </div>
  );
}
