import { useEffect, useState } from 'react';
import { getChromeHost, type ChromeHost } from '@/lib/chromeHost';

export function useChromeHost(): ChromeHost | null {
  const [host, setHost] = useState<ChromeHost | null>(() =>
    typeof window === 'undefined' ? null : getChromeHost(),
  );

  useEffect(() => {
    const sync = () => {
      const next = getChromeHost();
      setHost(next);
      return next;
    };
    sync();
    window.addEventListener('pywebviewready', sync);
    window.addEventListener('agentus-chrome-ready', sync);
    const id = window.setInterval(() => {
      if (sync()) window.clearInterval(id);
    }, 50);
    const timeout = window.setTimeout(() => window.clearInterval(id), 4000);
    return () => {
      window.removeEventListener('pywebviewready', sync);
      window.removeEventListener('agentus-chrome-ready', sync);
      window.clearInterval(id);
      window.clearTimeout(timeout);
    };
  }, []);

  return host;
}
