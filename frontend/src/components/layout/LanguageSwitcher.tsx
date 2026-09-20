import { Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { LanguageFlag } from '@/components/layout/LanguageFlag';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  APP_LANGUAGES,
  LANGUAGE_LABEL_KEYS,
  resolveAppLanguage,
  setAppLanguage,
} from '@/i18n';

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { t, i18n } = useTranslation();
  const current = resolveAppLanguage(i18n.resolvedLanguage ?? i18n.language);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size={compact ? 'icon' : 'sm'} className="app-no-drag">
          <LanguageFlag code={current} />
          {!compact ? <span>{t('shell.language')}</span> : null}
          <span className="sr-only">{t('shell.language')}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="app-no-drag max-h-80 min-w-44 overflow-y-auto">
        {APP_LANGUAGES.map((code) => (
          <DropdownMenuItem
            key={code}
            className="gap-2"
            onClick={() => {
              void setAppLanguage(code);
            }}
          >
            <LanguageFlag code={code} />
            <span className="flex-1">{t(LANGUAGE_LABEL_KEYS[code])}</span>
            {current === code ? <Check className="size-4 shrink-0" /> : <span className="size-4 shrink-0" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
