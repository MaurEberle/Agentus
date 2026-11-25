import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ApiError, queryClient } from '@/api/client';
import { notify } from '@/lib/notifications';
import type { AgentNetworkDocument } from '@/modules/network/model/document';
import { copyNetworkVersion, restoreNetworkVersion, versionKeys } from '@/modules/network/versions/api';

export function versionStamp(iso: string, locale: string): string {
  try {
    return new Intl.DateTimeFormat(locale, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/** Restore and copy, shared by the versions dialog and the preview in the editor. */
export function useVersionActions({
  networkId,
  networkName,
  onRestored,
  onCopied,
}: {
  networkId: string | undefined;
  networkName: string;
  onRestored: (document: AgentNetworkDocument, from: number) => void;
  onCopied: (document: AgentNetworkDocument) => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<'restore' | 'copy' | null>(null);

  async function restore(version: number, baseRevision: number | undefined): Promise<boolean> {
    if (!networkId) return false;
    setBusy('restore');
    try {
      const restored = await restoreNetworkVersion(networkId, version, baseRevision);
      onRestored(restored, version);
      return true;
    } catch (error) {
      const key = error instanceof ApiError ? error.messageKey : undefined;
      if (key === 'networks.conflict') void queryClient.invalidateQueries({ queryKey: versionKeys.list(networkId) });
      notify({
        titleKey: key === 'networks.conflict' ? 'network.versions.conflict' : key === 'run.busy' ? 'network.versions.busy' : 'network.versions.error',
        variant: 'error',
      });
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function copy(version: number): Promise<void> {
    if (!networkId) return;
    setBusy('copy');
    try {
      const created = await copyNetworkVersion(networkId, version, t('network.versions.copyName', { name: networkName, version }));
      onCopied(created);
    } catch {
      notify({ titleKey: 'network.versions.error', variant: 'error' });
    } finally {
      setBusy(null);
    }
  }

  return { busy, restore, copy };
}
