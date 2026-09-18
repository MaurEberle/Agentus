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
import { setAppLanguage } from '@/i18n';

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { t, i18n } = useTranslation();
  const current = i18n.resolvedLanguage === 'en' ? 'en' : 'de';

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
          onValueChange={(value) => void setAppLanguage(value === 'en' ? 'en' : 'de')}
        >
          <DropdownMenuRadioItem value="de">{t('shell.languageDe')}</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="en">{t('shell.languageEn')}</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
