import type { ReactNode } from 'react';
import { Brain, Boxes, Eye, FileText, Layers, Tag, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Building blocks of the model detail (installed and Hugging Face): a head with name,
 * publisher and badges, key figures as tiles, then grouped sections. Most important first.
 */

export function DetailHero({
  title,
  publisher,
  badges,
  children,
}: {
  title: string;
  publisher?: string | null;
  badges?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="space-y-3 border-b bg-muted/30 p-4">
      <div className="space-y-0.5">
        <h2 className="text-base font-semibold leading-snug [overflow-wrap:anywhere]">{title}</h2>
        {publisher ? <p className="text-sm text-muted-foreground">{publisher}</p> : null}
      </div>
      {badges ? <div className="flex flex-wrap gap-1.5">{badges}</div> : null}
      {children}
    </div>
  );
}

export type KeyFact = { label: string; value: string | null | undefined; hint?: string };

// Pairs of tiles side by side from this pane width on, else stacked: 4 in a row or 2 x 2,
// never one tile alone in a second row (flex-basis switch, no container queries needed).
const PAIR_BASIS = 'calc((32rem - 100%) * 999)';

/** The few figures that decide whether a model fits: tiles, most important first. */
export function KeyFacts({ items }: { items: KeyFact[] }) {
  const shown = items.filter((item) => Boolean(item.value));
  if (shown.length === 0) return null;
  const pairs: KeyFact[][] = [];
  for (let index = 0; index < shown.length; index += 2) pairs.push(shown.slice(index, index + 2));
  return (
    <dl className="flex flex-wrap gap-2">
      {pairs.map((pair) => (
        <div key={pair[0].label} className="flex min-w-0 grow gap-2" style={{ flexBasis: PAIR_BASIS }}>
          {pair.map((item) => (
            <div key={item.label} className="min-w-0 flex-1 rounded-md border bg-background px-3 py-2" title={item.hint}>
              <dt className="truncate text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{item.label}</dt>
              <dd className="mt-0.5 truncate font-mono text-base font-semibold tabular-nums">{item.value}</dd>
            </div>
          ))}
        </div>
      ))}
    </dl>
  );
}

const FEATURE_ICONS = {
  tools: Wrench,
  thinking: Brain,
  vision: Eye,
  moe: Boxes,
  embedding: Layers,
  template: FileText,
  tag: Tag,
} as const;

export type FeatureKind = keyof typeof FEATURE_ICONS;

/**
 * A capability or kind as a chip: "Werkzeuge", "Denken", "MoE". ``strong`` for the model
 * type, ``live`` for a state such as "loaded" (green dot).
 */
export function FeatureBadge({
  kind,
  label,
  strong,
  live,
}: {
  kind?: FeatureKind;
  label: string;
  strong?: boolean;
  live?: boolean;
}) {
  const Icon = kind ? FEATURE_ICONS[kind] : null;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs',
        strong ? 'border-primary/40 bg-primary/10 font-medium text-primary' : 'bg-background text-foreground',
      )}
    >
      {live ? <span className="size-2 rounded-full bg-emerald-500" aria-hidden /> : null}
      {Icon ? <Icon className="size-3" aria-hidden /> : null}
      {label}
    </span>
  );
}

export type DetailRow = [label: string, value: ReactNode];

/** A titled group of label/value rows; rows without a value are left out. */
export function DetailSection({ title, rows, children }: { title: string; rows: DetailRow[]; children?: ReactNode }) {
  const shown = rows.filter(([, value]) => value !== null && value !== undefined && value !== '' && value !== false);
  if (shown.length === 0 && !children) return null;
  return (
    <section className="space-y-1.5">
      <h3 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{title}</h3>
      {shown.length > 0 ? (
        <dl className="divide-y rounded-md border text-sm">
          {shown.map(([label, value]) => (
            <div key={label} className="grid grid-cols-[8.5rem_minmax(0,1fr)] gap-3 px-3 py-1.5">
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="min-w-0 break-words">{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {children}
    </section>
  );
}

/** An external link that shows the address without "https://", wrapping where it must. */
export function ExternalLink({ href, children }: { href: string; children?: ReactNode }) {
  return (
    <a className="break-all text-primary underline-offset-2 hover:underline" href={href} target="_blank" rel="noreferrer">
      {children ?? href.replace(/^https?:\/\//, '')}
    </a>
  );
}
