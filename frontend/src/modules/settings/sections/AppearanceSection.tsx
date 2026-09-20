import { useTheme } from 'next-themes';
import { useTranslation } from 'react-i18next';
import { LanguageFlag } from '@/components/layout/LanguageFlag';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
  APP_LANGUAGES,
  LANGUAGE_LABEL_KEYS,
  LANGUAGE_NAME_KEYS,
  formatLanguageOptionLabel,
  isAppLanguage,
  resolveAppLanguage,
  setAppLanguage,
  type AppLanguage,
} from '@/i18n';
import { notify } from '@/lib/notifications';
import { patchSettings } from '@/modules/settings/api';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';
import { useAppStore } from '@/store';

function LanguageOptionLabel({ code }: { code: AppLanguage }) {
  const { t } = useTranslation();
  const label = formatLanguageOptionLabel(t(LANGUAGE_LABEL_KEYS[code]), t(LANGUAGE_NAME_KEYS[code]));
  return (
    <span className="flex min-w-0 items-center gap-2 text-left">
      <LanguageFlag code={code} />
      <span className="truncate">{label}</span>
    </span>
  );
}

export function AppearanceSection() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const language = resolveAppLanguage(i18n.resolvedLanguage ?? i18n.language);
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
        <div className="space-y-2">
          <Label htmlFor="settings-language">{t('shell.language')}</Label>
          <Select
            value={language}
            onValueChange={(value) => {
              if (isAppLanguage(value)) void setAppLanguage(value);
            }}
          >
            <SelectTrigger id="settings-language" className="max-w-sm">
              <LanguageOptionLabel code={language} />
            </SelectTrigger>
            <SelectContent>
              {APP_LANGUAGES.map((code) => (
                <SelectItem key={code} value={code}>
                  <LanguageOptionLabel code={code} />
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
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
