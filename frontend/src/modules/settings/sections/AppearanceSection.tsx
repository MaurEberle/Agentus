import { useTheme } from 'next-themes';
import { useTranslation } from 'react-i18next';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Switch } from '@/components/ui/switch';
import { setAppLanguage } from '@/i18n';
import { notify } from '@/lib/notifications';
import { patchSettings } from '@/modules/settings/api';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';
import { useAppStore } from '@/store';

export function AppearanceSection() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const language = i18n.resolvedLanguage === 'en' ? 'en' : 'de';
  const fabVisible = useAppStore((state) => state.helpChatFabVisible);
  const setHelpChatFabVisible = useAppStore((state) => state.setHelpChatFabVisible);

  return (
    <div className="max-w-xl">
      <SectionHeader title={t('settings.nav.appearance')} description={t('settings.appearance.lead')} />
      <div className="space-y-6">
        <fieldset className="space-y-3">
          <legend className="text-sm font-medium">{t('shell.theme')}</legend>
          <RadioGroup
            value={theme ?? 'system'}
            onValueChange={setTheme}
            className="grid gap-2"
          >
            {(
              [
                ['light', 'shell.themeLight'],
                ['dark', 'shell.themeDark'],
                ['system', 'shell.themeSystem'],
              ] as const
            ).map(([value, key]) => (
              <label key={value} className="flex items-center gap-2 text-sm">
                <RadioGroupItem value={value} id={`theme-${value}`} />
                <span>{t(key)}</span>
              </label>
            ))}
          </RadioGroup>
        </fieldset>
        <fieldset className="space-y-3">
          <legend className="text-sm font-medium">{t('shell.language')}</legend>
          <RadioGroup
            value={language}
            onValueChange={(value) => void setAppLanguage(value === 'en' ? 'en' : 'de')}
            className="grid gap-2"
          >
            <label className="flex items-center gap-2 text-sm">
              <RadioGroupItem value="de" id="lang-de" />
              <span>{t('shell.languageDe')}</span>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <RadioGroupItem value="en" id="lang-en" />
              <span>{t('shell.languageEn')}</span>
            </label>
          </RadioGroup>
        </fieldset>
        <div className="flex items-center justify-between gap-4 rounded-md border p-3">
          <div>
            <Label htmlFor="fab-toggle">{t('settings.appearance.fab')}</Label>
            <p className="text-xs text-muted-foreground">{t('settings.appearance.fabHint')}</p>
          </div>
          <Switch
            id="fab-toggle"
            checked={fabVisible}
            onCheckedChange={(checked) => {
              setHelpChatFabVisible(checked);
              void patchSettings({ helpChatFabVisible: checked }).then(() => {
                notify({
                  titleKey: 'settings.notify.saved',
                  variant: 'success',
                });
              });
            }}
          />
        </div>
      </div>
    </div>
  );
}
