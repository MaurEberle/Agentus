import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { useAboutQuery, useStoresQuery } from '@/modules/settings/api';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';

export function AboutSection() {
  const { t } = useTranslation();
  const { data: about } = useAboutQuery();
  const { data: location } = useStoresQuery();
  const uiVersion = import.meta.env.VITE_APP_VERSION ?? '0.1.0';
  const folderName = location?.dataDir.split(/[/\\]/).filter(Boolean).at(-1) ?? '—';
  const okStores = location?.stores.filter((store) => store.state === 'ok').length ?? 0;

  return (
    <div className="max-w-xl space-y-4">
      <SectionHeader title={t('settings.nav.about')} description={t('settings.about.lead')} />
      <dl className="grid gap-3 text-sm">
        <div className="flex justify-between gap-4 border-b py-2">
          <dt className="text-muted-foreground">{t('settings.about.uiVersion')}</dt>
          <dd className="font-mono">{uiVersion}</dd>
        </div>
        <div className="flex justify-between gap-4 border-b py-2">
          <dt className="text-muted-foreground">{t('settings.about.apiVersion')}</dt>
          <dd className="font-mono">{about?.apiVersion ?? '—'}</dd>
        </div>
        <div className="flex items-center justify-between gap-4 border-b py-2">
          <dt className="text-muted-foreground">{t('settings.about.runtime')}</dt>
          <dd>
            <Badge variant={about?.runtime?.ok ? 'default' : 'secondary'}>
              {about?.runtime?.ok ? t('settings.runtime.status.ok') : t('settings.runtime.status.unknown')}
            </Badge>
          </dd>
        </div>
        <div className="flex justify-between gap-4 border-b py-2">
          <dt className="text-muted-foreground">{t('settings.about.dataFolder')}</dt>
          <dd>{folderName}</dd>
        </div>
        <div className="flex justify-between gap-4 py-2">
          <dt className="text-muted-foreground">{t('settings.about.storesOk')}</dt>
          <dd>
            {okStores}/{location?.stores.length ?? 0}
          </dd>
        </div>
      </dl>
    </div>
  );
}
