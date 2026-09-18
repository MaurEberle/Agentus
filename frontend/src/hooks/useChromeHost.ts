import { useEffect, useState } from 'react';
import { getChromeHost, type ChromeHost } from '@/lib/chromeHost';

export function useChromeHost(): ChromeHost | null {
  const [host, setHost] = useState<ChromeHost | null>(null);

  useEffect(() => {
    setHost(getChromeHost());
  }, []);

  return host;
}
