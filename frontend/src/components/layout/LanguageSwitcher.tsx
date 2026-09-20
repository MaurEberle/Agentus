import { Check, Languages } from 'lucide-react';
import { useTranslation } from 'react-i18next';
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
  type AppLanguage,
} from '@/i18n';

function LanguageFlag({ code }: { code: AppLanguage }) {
  const className = 'size-4 shrink-0 overflow-hidden rounded-[2px]';
  if (code === 'de') {
    return (
      <svg viewBox="0 0 5 3" className={className} aria-hidden>
        <rect width="5" height="1" fill="#000" />
        <rect y="1" width="5" height="1" fill="#DD0000" />
        <rect y="2" width="5" height="1" fill="#FFCE00" />
      </svg>
    );
  }
  if (code === 'es') {
    return (
      <svg viewBox="0 0 6 4" className={className} aria-hidden>
        <rect width="6" height="4" fill="#AA151B" />
        <rect y="1" width="6" height="2" fill="#F1BF00" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 60 30" className={className} aria-hidden>
      <rect width="60" height="30" fill="#012169" />
      <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6" />
      <path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" strokeWidth="4" />
      <path d="M30,0 v30 M0,15 h60" stroke="#fff" strokeWidth="10" />
      <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
    </svg>
  );
}

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
            <LanguageFlag code={code} />
            <span className="flex-1">{t(LANGUAGE_LABEL_KEYS[code])}</span>
            {current === code ? <Check className="size-4 shrink-0" /> : <span className="size-4 shrink-0" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
