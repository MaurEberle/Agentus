import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
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

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <HeadButton label={t('history.table.network')} onClick={() => toggle('networkName')} />
          <HeadButton label={t('history.table.runs')} onClick={() => toggle('runs')} />
          <HeadButton label={t('history.table.succeeded')} onClick={() => toggle('succeeded')} />
          <HeadButton label={t('history.table.failed')} onClick={() => toggle('failed')} />
          <HeadButton label={t('history.table.cancelled')} onClick={() => toggle('cancelled')} />
          <HeadButton label={t('history.table.median')} onClick={() => toggle('medianMs')} />
          <TableHead>{t('history.table.topErrorNode')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((row) => (
          <TableRow key={row.networkId}>
            <TableCell className="font-medium">{row.networkName}</TableCell>
            <TableCell className="tabular-nums">{formatInt(row.runs, locale)}</TableCell>
            <TableCell className="tabular-nums">{formatInt(row.succeeded, locale)}</TableCell>
            <TableCell className="tabular-nums">{formatInt(row.failed, locale)}</TableCell>
            <TableCell className="tabular-nums">{formatInt(row.cancelled, locale)}</TableCell>
            <TableCell className="tabular-nums">{row.medianMs === null ? '—' : formatDuration(row.medianMs)}</TableCell>
            <TableCell>{row.topErrorNode ?? '—'}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
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
