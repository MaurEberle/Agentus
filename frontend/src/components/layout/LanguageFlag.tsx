import { cn } from '@/lib/utils';
import type { AppLanguage } from '@/i18n/languages';

export function LanguageFlag({
  code,
  className,
}: {
  code: AppLanguage;
  className?: string;
}) {
  const frame = cn('size-4 shrink-0 overflow-hidden rounded-[2px]', className);
  if (code === 'de') {
    return (
      <svg viewBox="0 0 5 3" className={frame} aria-hidden>
        <rect width="5" height="1" fill="#000" />
        <rect y="1" width="5" height="1" fill="#DD0000" />
        <rect y="2" width="5" height="1" fill="#FFCE00" />
      </svg>
    );
  }
  if (code === 'es') {
    return (
      <svg viewBox="0 0 6 4" className={frame} aria-hidden>
        <rect width="6" height="4" fill="#AA151B" />
        <rect y="1" width="6" height="2" fill="#F1BF00" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 60 30" className={frame} aria-hidden>
      <rect width="60" height="30" fill="#012169" />
      <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6" />
      <path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" strokeWidth="4" />
      <path d="M30,0 v30 M0,15 h60" stroke="#fff" strokeWidth="10" />
      <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
    </svg>
  );
}
