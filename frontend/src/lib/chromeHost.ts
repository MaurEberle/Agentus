export interface ChromeHost {
  minimize: () => void;
  maximize: () => void;
  restore: () => void;
  close: () => void;
  isMaximized: () => boolean | Promise<boolean>;
  pickFolder?: () => Promise<string | null>;
}

type PywebviewApi = Partial<ChromeHost> & Record<string, unknown>;

declare global {
  interface Window {
    chromeHost?: ChromeHost;
    pywebview?: { api?: PywebviewApi };
  }
}

function asChromeHost(api: Partial<ChromeHost> | undefined | null): ChromeHost | null {
  if (!api || typeof api.minimize !== 'function') return null;
  return {
    minimize: () => void api.minimize?.(),
    maximize: () => void api.maximize?.(),
    restore: () => void api.restore?.(),
    close: () => void api.close?.(),
    isMaximized: () => api.isMaximized?.() ?? false,
    pickFolder: api.pickFolder
      ? async () => {
          const value = await api.pickFolder?.();
          return value ?? null;
        }
      : undefined,
  };
}

export function getChromeHost(): ChromeHost | null {
  if (typeof window === 'undefined') return null;
  const aliased = asChromeHost(window.chromeHost);
  if (aliased) return aliased;
  const wrapped = asChromeHost(window.pywebview?.api);
  if (wrapped) {
    window.chromeHost = wrapped;
  }
  return wrapped;
}
