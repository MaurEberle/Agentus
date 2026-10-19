import type { KeyboardEvent as ReactKeyboardEvent } from 'react';

const FIELD = 'textarea, input, select, [contenteditable="true"]';

/** The marked primary button, otherwise the last enabled action button. */
export function dialogPrimaryButton(root: HTMLElement): HTMLButtonElement | null {
  const marked = root.querySelector<HTMLButtonElement>('button[data-dialog-primary]:not(:disabled)');
  if (marked) return marked;
  const buttons = [...root.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')].filter(
    (button) => button.dataset.dialogClose !== 'true',
  );
  return buttons.at(-1) ?? null;
}

export function focusDialogPrimary(root: HTMLElement) {
  dialogPrimaryButton(root)?.focus();
}

export function onDialogKeyDown(event: ReactKeyboardEvent<HTMLElement>) {
  const root = event.currentTarget;
  const target = event.target;
  if (!(target instanceof HTMLElement) || !root.contains(target)) return;
  if (event.key === ' ') {
    if (target.closest(FIELD)) return;
    return;
  }
  if (event.key !== 'Enter' || event.defaultPrevented) return;
  if (target.closest('textarea, [contenteditable="true"]')) return;
  const primary = dialogPrimaryButton(root);
  if (!primary) return;
  event.preventDefault();
  primary.click();
}
