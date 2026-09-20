import { Check, Languages } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { APP_LANGUAGES, LANGUAGE_LABEL_KEYS, resolveAppLanguage, setAppLanguage } from '@/i18n';

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
      <DropdownMenuContent align="end" className="app-no-drag min-w-40">
        {APP_LANGUAGES.map((code) => (
          <DropdownMenuItem
            key={code}
            className="gap-2"
            onClick={() => {
              void setAppLanguage(code);
            }}
          >
            <span className="flex size-4 shrink-0 items-center justify-center text-[10px] font-semibold uppercase leading-none">
              {code}
            </span>
            <span className="flex-1">{t(LANGUAGE_LABEL_KEYS[code])}</span>
            {current === code ? <Check className="size-4 shrink-0" /> : <span className="size-4 shrink-0" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
