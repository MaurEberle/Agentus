import { Languages } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { APP_LANGUAGES, LANGUAGE_LABEL_KEYS, isAppLanguage, resolveAppLanguage, setAppLanguage } from '@/i18n';

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { t, i18n } = useTranslation();
  const current = resolveAppLanguage(i18n.resolvedLanguage ?? i18n.language);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size={compact ? 'icon' : 'sm'} className="app-no-drag">
          <Languages className="size-4" />
          {!compact ? <span>{t('shell.language')}</span> : null}
          <span className="sr-only">{t('shell.language')}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="app-no-drag">
        <DropdownMenuRadioGroup
          value={current}
          onValueChange={(value) => {
            if (isAppLanguage(value)) void setAppLanguage(value);
          }}
        >
          {APP_LANGUAGES.map((code) => (
            <DropdownMenuRadioItem key={code} value={code}>
              {t(LANGUAGE_LABEL_KEYS[code])}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
