import { useEffect, type RefObject } from 'react';

/** True while the user has a non-empty selection inside root. */
export function selectionInside(root: HTMLElement | null): boolean {
  if (!root) return false;
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) return false;
  const node = selection.anchorNode;
  return Boolean(node && root.contains(node));
}

/**
 * pywebview turns selection off for the whole window. Chat roots opt back in
 * with `select-text`. Ctrl+C still has to copy that selection: the desktop
 * window has no context menu, and a focused composer would otherwise swallow it.
 */
export function useCopySelection(rootRef: RefObject<HTMLElement | null>) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented) return;
      if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return;
      if (event.key.toLowerCase() !== 'c') return;
      const root = rootRef.current;
      const selection = window.getSelection();
      if (!root || !selection || selection.isCollapsed) return;
      const text = selection.toString();
      const node = selection.anchorNode;
      if (!text || !node || !root.contains(node)) return;
      const target = event.target;
      if (
        (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) &&
        target.selectionStart !== target.selectionEnd
      ) {
        return;
      }
      if (target instanceof HTMLElement && target.isContentEditable) return;
      event.preventDefault();
      void navigator.clipboard.writeText(text).catch(() => undefined);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [rootRef]);
}
