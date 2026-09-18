export interface ChromeHost {
  minimize: () => void;
  maximize: () => void;
  restore: () => void;
  close: () => void;
  isMaximized: () => boolean;
  pickFolder?: () => Promise<string | null>;
}

declare global {
  interface Window {
    chromeHost?: ChromeHost;
  }
}

export function getChromeHost(): ChromeHost | null {
  if (typeof window === 'undefined') return null;
  return window.chromeHost ?? null;
}
