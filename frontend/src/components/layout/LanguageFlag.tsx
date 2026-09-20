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
  if (code === 'fr') {
    return (
      <svg viewBox="0 0 3 2" className={frame} aria-hidden>
        <rect width="1" height="2" fill="#002395" />
        <rect x="1" width="1" height="2" fill="#fff" />
        <rect x="2" width="1" height="2" fill="#ED2939" />
      </svg>
    );
  }
  if (code === 'tr') {
    return (
      <svg viewBox="0 0 12 8" className={frame} aria-hidden>
        <rect width="12" height="8" fill="#E30A17" />
        <circle cx="4.25" cy="4" r="2" fill="#fff" />
        <circle cx="4.85" cy="4" r="1.55" fill="#E30A17" />
        <polygon
          fill="#fff"
          points="6.55,2.7 6.95,3.55 7.9,3.55 7.15,4.1 7.45,4.95 6.55,4.4 5.65,4.95 5.95,4.1 5.2,3.55 6.15,3.55"
        />
      </svg>
    );
  }
  if (code === 'pt') {
    return (
      <svg viewBox="0 0 10 6" className={frame} aria-hidden>
        <rect width="10" height="6" fill="#FF0000" />
        <rect width="4" height="6" fill="#006600" />
        <circle cx="4" cy="3" r="1.15" fill="#FFD700" />
        <circle cx="4" cy="3" r="0.7" fill="#002776" />
      </svg>
    );
  }
  if (code === 'zh') {
    return (
      <svg viewBox="0 0 12 8" className={frame} aria-hidden>
        <rect width="12" height="8" fill="#DE2910" />
        <polygon
          fill="#FFDE00"
          points="2.4,1.35 2.7,2.25 3.65,2.25 2.88,2.8 3.18,3.7 2.4,3.15 1.62,3.7 1.92,2.8 1.15,2.25 2.1,2.25"
        />
      </svg>
    );
  }
  if (code === 'ja') {
    return (
      <svg viewBox="0 0 12 8" className={frame} aria-hidden>
        <rect width="12" height="8" fill="#fff" />
        <circle cx="6" cy="4" r="2.2" fill="#BC002D" />
      </svg>
    );
  }
  if (code === 'ar') {
    return (
      <svg viewBox="0 0 12 8" className={frame} aria-hidden>
        <rect width="12" height="8" fill="#006C35" />
        <rect x="1.5" y="5.6" width="9" height="0.45" fill="#fff" />
        <path fill="#fff" d="M2.2 5.4 L10 5.4 L9.4 5.85 L2.6 5.85 Z" />
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
