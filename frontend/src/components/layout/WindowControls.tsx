import { useEffect } from 'react';
import { Maximize2, Minimize2, Minus, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { useChromeHost } from '@/hooks/useChromeHost';
import { useAppStore } from '@/store';

export function WindowControls() {
  const { t } = useTranslation();
  const host = useChromeHost();
  const maximized = useAppStore((state) => state.windowMaximized);
  const setWindowMaximized = useAppStore((state) => state.setWindowMaximized);

  useEffect(() => {
    if (host) setWindowMaximized(host.isMaximized());
  }, [host, setWindowMaximized]);

  if (!host) return null;

  return (
    <div className="app-no-drag flex items-center">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={t('shell.window.minimize')}
        onClick={() => host.minimize()}
      >
        <Minus className="size-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={t(maximized ? 'shell.window.restore' : 'shell.window.maximize')}
        onClick={() => {
          if (maximized) {
            host.restore();
            setWindowMaximized(false);
          } else {
            host.maximize();
            setWindowMaximized(true);
          }
        }}
      >
        {maximized ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="hover:bg-destructive hover:text-destructive-foreground"
        aria-label={t('shell.window.close')}
        onClick={() => host.close()}
      >
        <X className="size-4" />
      </Button>
    </div>
  );
}
