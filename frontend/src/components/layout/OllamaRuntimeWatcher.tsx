import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { notify } from '@/lib/notifications';
import { OLLAMA_RUNTIME_ACTION, OLLAMA_RUNTIME_PATH, ollamaMessageKey } from '@/lib/ollamaRuntime';
import { useOllamaRuntimeQuery } from '@/modules/settings/api';

// Once per app start and version: the hint comes back after a restart until it is taken over.
const announced = new Set<string>();

/** Tells the user about a newer installed Ollama and about problems with the own copy. */
export function OllamaRuntimeWatcher() {
  const navigate = useNavigate();
  const { data } = useOllamaRuntimeQuery();
  const update = data?.mode === 'own' ? data.updateVersion : null;
  const current = data?.version ?? '';
  const problem = data?.mode === 'own' ? data.messageKey : null;

  useEffect(() => {
    if (!update || announced.has(`update:${update}`)) return;
    announced.add(`update:${update}`);
    notify({
      titleKey: 'notify.ollamaUpdate.title',
      descriptionKey: 'notify.ollamaUpdate.desc',
      values: { version: update, current },
      variant: 'info',
      action: OLLAMA_RUNTIME_ACTION,
      duration: 20_000,
      toastAction: {
        labelKey: 'notify.ollamaUpdate.action',
        onClick: () => navigate(OLLAMA_RUNTIME_PATH),
      },
    });
  }, [current, navigate, update]);

  useEffect(() => {
    // "No installed Ollama" is normal for cloud-only use; only real failures are announced.
    if (!problem || problem === 'runtime.own.noSource' || announced.has(`problem:${problem}`)) return;
    const titleKey = ollamaMessageKey(problem);
    if (!titleKey) return;
    announced.add(`problem:${problem}`);
    notify({
      titleKey,
      values: data?.messageParams ?? {},
      variant: problem === 'runtime.own.rolledBack' ? 'warning' : 'error',
      action: OLLAMA_RUNTIME_ACTION,
    });
  }, [data?.messageParams, problem]);

  return null;
}
