import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
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

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <HeadButton label={t('history.table.model')} onClick={() => toggle('model')} />
          <TableHead>{t('history.table.provider')}</TableHead>
          <HeadButton label={t('history.table.calls')} onClick={() => toggle('calls')} />
          <HeadButton label={t('history.table.ok')} onClick={() => toggle('ok')} />
          <HeadButton label={t('history.table.callErrors')} onClick={() => toggle('error')} />
          <HeadButton label={t('history.table.errorRate')} onClick={() => toggle('errorRate')} />
          <HeadButton label={t('history.table.median')} onClick={() => toggle('medianMs')} />
          <HeadButton label={t('history.table.tokensIn')} onClick={() => toggle('tokensIn')} />
          <HeadButton label={t('history.table.tokensOut')} onClick={() => toggle('tokensOut')} />
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((row) => (
          <TableRow key={`${row.provider}:${row.model}`}>
            <TableCell className="font-mono text-xs">{row.model}</TableCell>
            <TableCell>{t(`history.provider.${row.provider}`)}</TableCell>
            <TableCell className="tabular-nums">{formatInt(row.calls, locale)}</TableCell>
            <TableCell className="tabular-nums">{formatInt(row.ok, locale)}</TableCell>
            <TableCell className="tabular-nums">{formatInt(row.error, locale)}</TableCell>
            <TableCell className="tabular-nums">{formatPercent(row.errorRate * 100, locale)}</TableCell>
            <TableCell className="tabular-nums">{row.medianMs === null ? '—' : formatDuration(row.medianMs)}</TableCell>
            <TableCell className="tabular-nums">{row.tokensIn === null ? '—' : formatInt(row.tokensIn, locale)}</TableCell>
            <TableCell className="tabular-nums">{row.tokensOut === null ? '—' : formatInt(row.tokensOut, locale)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function sortValue(row: ModelAggRow, key: SortKey): string | number | null {
  if (key === 'model') return row.model;
  return row[key];
}

function HeadButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <TableHead>
      <button type="button" className="font-medium hover:underline" onClick={onClick}>
        {label}
      </button>
    </TableHead>
  );
}
