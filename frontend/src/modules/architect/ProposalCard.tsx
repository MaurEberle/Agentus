import { FileInput, PackageCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import type { Proposal } from '@/modules/architect/api';

/**
 * What the architect asked for and waits on: reading a network in (E-6) or the closing dialog (E-5).
 * Nothing happens until the user clicks.
 */
export function ProposalCard({
  proposal,
  busy,
  cloud,
  hasDraft,
  onLoad,
  onOpenClosing,
  onDismiss,
}: {
  proposal: Proposal;
  busy: boolean;
  cloud: boolean;
  hasDraft: boolean;
  onLoad: () => void;
  onOpenClosing: () => void;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  const load = proposal.kind === 'load';
  const Icon = load ? FileInput : PackageCheck;
  return (
    <div className="border-t bg-muted/40 px-3 py-2.5 text-sm" role="status">
      <div className="flex gap-2">
        <Icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        <div className="min-w-0 flex-1">
          <p>
            {load
              ? t('architect.load.ask', { name: proposal.name, purpose: t(`architect.load.purpose.${proposal.purpose}`) })
              : t(`architect.proposal.${proposal.kind}`)}
          </p>
          {load && (hasDraft || cloud) ? (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {[hasDraft ? t('architect.load.replaces') : '', cloud ? t('architect.load.cloudNote') : ''].filter(Boolean).join(' ')}
            </p>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-2">
            <Button type="button" size="sm" loading={busy} disabled={busy} onClick={load ? onLoad : onOpenClosing}>
              {load ? t('architect.load.confirm') : t('architect.proposal.open')}
            </Button>
            <Button type="button" size="sm" variant="outline" disabled={busy} onClick={onDismiss}>
              {load ? t('architect.load.decline') : t('architect.proposal.dismiss')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
