import { GitCommitHorizontal, Waypoints } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { NetworkKind } from '@/modules/dashboard/model';
import { cn } from '@/lib/utils';

/** How the network runs: a chief that delegates (orchestrator) or a chain of steps (linear). */
export function KindBadge({ kind }: { kind?: NetworkKind }) {
  const { t } = useTranslation();
  if (!kind) return <span className="text-muted-foreground">—</span>;
  const Icon = kind === 'orchestrator' ? Waypoints : GitCommitHorizontal;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs',
        kind === 'orchestrator' ? 'border-primary/40 bg-primary/10 text-primary' : 'text-foreground',
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {t(`networks.kind.${kind}`)}
    </span>
  );
}
