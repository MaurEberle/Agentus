/** Bell entries with this action open the runtime settings. */
export const OLLAMA_RUNTIME_ACTION = 'open-ollama-runtime';
export const OLLAMA_RUNTIME_PATH = '/settings#runtime';

/** ``runtime.own.diskFull`` → ``settings.runtime.own.messages.diskFull``. */
export function ollamaMessageKey(key: string | null | undefined): string | null {
  if (!key) return null;
  if (key === 'app.restart.busy') return 'settings.runtime.own.messages.restartBusy';
  if (key.startsWith('runtime.own.')) {
    return `settings.runtime.own.messages.${key.slice('runtime.own.'.length)}`;
  }
  return null;
}
