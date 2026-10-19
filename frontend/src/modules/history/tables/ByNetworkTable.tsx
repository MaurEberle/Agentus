import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { COL_FIT, COL_TEXT, HistoryGrid, HistoryRow, historyCellClass, historyHeadClass } from '@/modules/history/HistoryGrid';
import { formatDuration, formatInt } from '@/modules/history/model/format';
import type { NetworkAggRow } from '@/modules/history/model/types';

type SortKey = 'networkName' | 'runs' | 'succeeded' | 'failed' | 'cancelled' | 'medianMs';

export function ByNetworkTable({ rows }: { rows: NetworkAggRow[] }) {
  const { t, i18n } = useTranslation();
  const [sortKey, setSortKey] = useState<SortKey>('runs');
  const [dir, setDir] = useState<'asc' | 'desc'>('desc');
  const locale = i18n.language;

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === 'string' && typeof bv === 'string') {
        return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      const an = Number(av ?? -1);
      const bn = Number(bv ?? -1);
      return dir === 'asc' ? an - bn : bn - an;
    });
    return copy;
  }, [dir, rows, sortKey]);

  function toggle(key: SortKey) {
    if (sortKey === key) setDir((value) => (value === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setDir(key === 'networkName' ? 'asc' : 'desc');
    }
  }

  if (rows.length === 0) {
    return <p className="p-4 text-sm text-muted-foreground">{t('history.empty.filtered')}</p>;
  }

  const columns = [COL_TEXT, COL_FIT, COL_FIT, COL_FIT, COL_FIT, COL_FIT, COL_TEXT].join(' ');

  return (
    <HistoryGrid columns={columns}>
      <HistoryRow className="hover:bg-transparent">
        <HeadButton label={t('history.table.network')} onClick={() => toggle('networkName')} />
        <HeadButton label={t('history.table.runs')} onClick={() => toggle('runs')} />
        <HeadButton label={t('history.table.succeeded')} onClick={() => toggle('succeeded')} />
        <HeadButton label={t('history.table.failed')} onClick={() => toggle('failed')} />
        <HeadButton label={t('history.table.cancelled')} onClick={() => toggle('cancelled')} />
        <HeadButton label={t('history.table.median')} onClick={() => toggle('medianMs')} />
        <div className={historyHeadClass} title={t('history.table.topErrorNode')}>{t('history.table.topErrorNode')}</div>
      </HistoryRow>
      {sorted.map((row) => (
        <HistoryRow key={row.networkId}>
          <div className={`${historyCellClass} font-medium`} title={row.networkName}>{row.networkName}</div>
          <div className={`${historyCellClass} tabular-nums`}>{formatInt(row.runs, locale)}</div>
          <div className={`${historyCellClass} tabular-nums`}>{formatInt(row.succeeded, locale)}</div>
          <div className={`${historyCellClass} tabular-nums`}>{formatInt(row.failed, locale)}</div>
          <div className={`${historyCellClass} tabular-nums`}>{formatInt(row.cancelled, locale)}</div>
          <div className={`${historyCellClass} tabular-nums`}>{row.medianMs === null ? '—' : formatDuration(row.medianMs)}</div>
          <div className={historyCellClass} title={row.topErrorNode ?? undefined}>{row.topErrorNode ?? '—'}</div>
        </HistoryRow>
      ))}
    </HistoryGrid>
  );
}

function HeadButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <div className={historyHeadClass} title={label}>
      <button type="button" className="max-w-full truncate text-left font-medium hover:underline" onClick={onClick}>
        {label}
      </button>
    </div>
  );
}
