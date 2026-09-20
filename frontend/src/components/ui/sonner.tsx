import { useTheme } from 'next-themes';
import { Toaster as Sonner } from 'sonner';
import { useMediaQuery } from '@/hooks/useMediaQuery';

export function Toaster() {
  const { resolvedTheme } = useTheme();
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');

  return (
    <Sonner
      theme={resolvedTheme === 'dark' ? 'dark' : 'light'}
      position="bottom-left"
      closeButton
      duration={reducedMotion ? 8000 : 4000}
      visibleToasts={3}
      toastOptions={{
        classNames: {
          toast: 'border-border bg-popover text-popover-foreground',
        },
      }}
    />
  );
}
