import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { COL_FIT, COL_TEXT, HistoryGrid, HistoryRow, historyCellClass, historyHeadClass } from '@/modules/history/HistoryGrid';
import { formatDuration, formatInt, formatPercent } from '@/modules/history/model/format';
import type { ModelAggRow } from '@/modules/history/model/types';

type SortKey = 'calls' | 'ok' | 'error' | 'errorRate' | 'medianMs' | 'tokensIn' | 'tokensOut' | 'model';

export function ByModelTable({ rows }: { rows: ModelAggRow[] }) {
  const { t, i18n } = useTranslation();
  const [sortKey, setSortKey] = useState<SortKey>('calls');
  const [dir, setDir] = useState<'asc' | 'desc'>('desc');
  const locale = i18n.language;

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
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
      setDir(key === 'model' ? 'asc' : 'desc');
    }
  }

  if (rows.length === 0) {
    return <p className="p-4 text-sm text-muted-foreground">{t('history.empty.filtered')}</p>;
  }

  const columns = [COL_TEXT, COL_FIT, COL_FIT, COL_FIT, COL_FIT, COL_FIT, COL_FIT, COL_FIT, COL_FIT].join(' ');

  return (
    <HistoryGrid columns={columns}>
      <HistoryRow className="hover:bg-transparent">
        <HeadButton label={t('history.table.model')} onClick={() => toggle('model')} />
        <div className={historyHeadClass} title={t('history.table.provider')}>{t('history.table.provider')}</div>
        <HeadButton label={t('history.table.calls')} onClick={() => toggle('calls')} />
        <HeadButton label={t('history.table.ok')} onClick={() => toggle('ok')} />
        <HeadButton label={t('history.table.callErrors')} onClick={() => toggle('error')} />
        <HeadButton label={t('history.table.errorRate')} onClick={() => toggle('errorRate')} />
        <HeadButton label={t('history.table.median')} onClick={() => toggle('medianMs')} />
        <HeadButton label={t('history.table.tokensIn')} onClick={() => toggle('tokensIn')} />
        <HeadButton label={t('history.table.tokensOut')} onClick={() => toggle('tokensOut')} />
      </HistoryRow>
      {sorted.map((row) => (
        <HistoryRow key={`${row.provider}:${row.model}`}>
          <div className={cnCell('font-mono text-xs')} title={row.model}>{row.model}</div>
          <div className={historyCellClass}>{t(`history.provider.${row.provider}`)}</div>
          <div className={cnCell('tabular-nums')}>{formatInt(row.calls, locale)}</div>
          <div className={cnCell('tabular-nums')}>{formatInt(row.ok, locale)}</div>
          <div className={cnCell('tabular-nums')}>{formatInt(row.error, locale)}</div>
          <div className={cnCell('tabular-nums')}>{formatPercent(row.errorRate * 100, locale)}</div>
          <div className={cnCell('tabular-nums')}>{row.medianMs === null ? '—' : formatDuration(row.medianMs)}</div>
          <div className={cnCell('tabular-nums')}>{row.tokensIn === null ? '—' : formatInt(row.tokensIn, locale)}</div>
          <div className={cnCell('tabular-nums')}>{row.tokensOut === null ? '—' : formatInt(row.tokensOut, locale)}</div>
        </HistoryRow>
      ))}
    </HistoryGrid>
  );
}

function cnCell(extra: string) {
  return `${historyCellClass} ${extra}`;
}

function sortValue(row: ModelAggRow, key: SortKey): string | number | null {
  if (key === 'model') return row.model;
  return row[key];
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
