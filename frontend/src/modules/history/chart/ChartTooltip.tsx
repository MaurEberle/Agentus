import { useTranslation } from 'react-i18next';
import { OUTCOME_FILL, type ChartOutcome } from '@/modules/history/chart/chartModel';

export type TooltipState = {
  /** Anchor in pixels inside the chart box: centre of the mark, its top. */
  x: number;
  y: number;
  title: string;
  /** Strong headline, e.g. "12 runs"; optional. */
  lead?: string;
  rows: { key: ChartOutcome; value: number; share?: number }[];
  note?: string;
};

/**
 * One tooltip for every chart view: the value leads, the name follows, a short stroke of
 * the series colour keys the row. It flips to the left near the right edge.
 */
export function ChartTooltip({ state, width }: { state: TooltipState | null; width: number }) {
  const { t, i18n } = useTranslation();
  if (!state) return null;
  const number = new Intl.NumberFormat(i18n.language);
  const flip = state.x > width - 180;
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-20 min-w-[9rem] rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md"
      style={{
        left: flip ? undefined : state.x + 12,
        right: flip ? Math.max(0, width - state.x + 12) : undefined,
        top: Math.max(0, state.y - 8),
      }}
    >
      <p className="text-muted-foreground">{state.title}</p>
      {state.lead ? <p className="text-sm font-semibold">{state.lead}</p> : null}
      {state.rows.length > 0 ? (
        <ul className="mt-1 space-y-0.5">
          {state.rows.map((row) => (
            <li key={row.key} className="flex items-center gap-2">
              <span className="h-0.5 w-3 shrink-0 rounded-full" style={{ background: OUTCOME_FILL[row.key] }} aria-hidden />
              <span className="font-semibold tabular-nums">{number.format(row.value)}</span>
              {row.share !== undefined ? <span className="tabular-nums text-muted-foreground">{row.share} %</span> : null}
              <span className="text-muted-foreground">{t(`history.outcome.${row.key}`)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {state.note ? <p className="mt-1 text-muted-foreground">{state.note}</p> : null}
    </div>
  );
}
