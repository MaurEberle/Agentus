import { useTheme } from 'next-themes';
import { Toaster as Sonner } from 'sonner';
import { useMediaQuery } from '@/hooks/useMediaQuery';

export function Toaster() {
  const { resolvedTheme } = useTheme();
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');

  return (
    <Sonner
      theme={resolvedTheme === 'dark' ? 'dark' : 'light'}
      position={isDesktop ? 'top-right' : 'bottom-center'}
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
