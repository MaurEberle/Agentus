import { Minus, Pencil, Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { NetworkDiff } from '@/modules/network/model/diff';

/** New, changed and removed nodes between two states (architect draft, versions). */
export function DiffList({ diff }: { diff: NetworkDiff }) {
  const { t } = useTranslation();
  const label = (id: string) => {
    const node = diff.nodes[id];
    if (!node) return id;
    const type = t(`network.palette.${node.type}`, { defaultValue: node.type });
    return node.label && node.label !== node.type ? `${node.label} (${type})` : type;
  };
  if (diff.empty) return <p className="text-xs text-muted-foreground">{t('network.diff.none')}</p>;
  return (
    <ul className="grid gap-1 text-xs">
      {diff.head.length > 0 ? (
        <li className="flex gap-1.5 text-warning">
          <Pencil className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>
            {t('network.diff.head', {
              fields: diff.head.map((key) => t(`network.diff.field.${key}`, { defaultValue: key })).join(', '),
            })}
          </span>
        </li>
      ) : null}
      {diff.added.map((id) => (
        <li key={`a${id}`} className="flex gap-1.5 text-primary">
          <Plus className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>
            <span className="sr-only">{t('network.diff.added')}: </span>
            {label(id)}
          </span>
        </li>
      ))}
      {diff.changed.map((item) => (
        <li key={`c${item.id}`} className="flex gap-1.5 text-warning">
          <Pencil className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span className="min-w-0">
            <span className="sr-only">{t('network.diff.changed')}: </span>
            {label(item.id)}
            <span className="text-muted-foreground"> · </span>
            <code className="break-all text-muted-foreground">{item.fields.join(', ')}</code>
          </span>
        </li>
      ))}
      {diff.removed.map((id) => (
        <li key={`r${id}`} className="flex gap-1.5 text-destructive">
          <Minus className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>
            <span className="sr-only">{t('network.diff.removed')}: </span>
            {label(id)}
          </span>
        </li>
      ))}
      {diff.edgesAdded.length + diff.edgesRemoved.length > 0 ? (
        <li className="text-muted-foreground">
          {t('network.diff.edges', { added: diff.edgesAdded.length, removed: diff.edgesRemoved.length })}
        </li>
      ) : null}
    </ul>
  );
}
