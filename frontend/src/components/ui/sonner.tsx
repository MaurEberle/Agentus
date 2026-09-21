import type { MouseEvent } from 'react';
import { useTheme } from 'next-themes';
import { toast, Toaster as Sonner } from 'sonner';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { useAppStore } from '@/store';

function onToastClick(event: MouseEvent<HTMLDivElement>) {
  const target = event.target;
  if (!(target instanceof Element)) return;
  const toastEl = target.closest('[data-sonner-toast]');
  if (!(toastEl instanceof HTMLElement)) return;
  const id = toastEl.getAttribute('data-testid');
  if (!id) return;
  useAppStore.getState().markRead(id);
  toast.dismiss(id);
}

export function Toaster() {
  const { resolvedTheme } = useTheme();
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');

  return (
    <div onClick={onToastClick}>
      <Sonner
        theme={resolvedTheme === 'dark' ? 'dark' : 'light'}
        position="bottom-left"
        closeButton
        duration={reducedMotion ? 8000 : 4000}
        visibleToasts={3}
        toastOptions={{
          classNames: {
            toast: 'cursor-pointer border-border bg-popover text-popover-foreground',
          },
        }}
      />
    </div>
  );
}
