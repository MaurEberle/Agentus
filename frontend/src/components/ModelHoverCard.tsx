import { useTranslation } from 'react-i18next';
import { formatBytes } from '@/lib/format';
import { formatParameters, modelLabel, type ModelFacts } from '@/lib/modelName';

/** Hover card of a model picker: full name, publisher, parameters, and what else the runtime knows. */
export function ModelHoverCard({ name, facts }: { name: string; facts?: ModelFacts }) {
  const { t, i18n } = useTranslation();
  const label = modelLabel(name);
  const quant = facts?.quantization ?? '';
  const rows: [string, string][] = [
    [t('models.detail.publisher'), label.publisher ?? ''],
    [t('models.detail.parameters'), formatParameters(facts?.parameterSize) ?? ''],
    // "hf.co/x/y:Q4_K_M" already shows its quantization in the name.
    [t('models.detail.quant'), quant && !label.name.toLowerCase().includes(quant.toLowerCase()) ? quant : ''],
    [t('models.detail.size'), facts?.sizeBytes ? formatBytes(facts.sizeBytes, i18n.language) : ''],
  ];
  const shown = rows.filter(([, value]) => value);
  return (
    <div className="grid max-w-80 gap-1.5">
      <p className="break-all font-medium">{label.name}</p>
      {shown.length > 0 ? (
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5">
          {shown.map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-muted-foreground">{key}</dt>
              <dd className="min-w-0 break-all">{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
