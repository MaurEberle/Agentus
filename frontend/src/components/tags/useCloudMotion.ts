import { useCallback, useLayoutEffect, useRef } from 'react';

type Box = { x: number; y: number; w: number; h: number };
type Seen = { key: string; host: HTMLElement | null; chips: Map<string, { box: Box; el: HTMLElement }>; height: number };

const MOVE: KeyframeAnimationOptions = { duration: 300, easing: 'cubic-bezier(0.2, 0, 0, 1)' };
const LEAVE: KeyframeAnimationOptions = { duration: 260, easing: 'cubic-bezier(0.4, 0, 1, 1)', fill: 'forwards' };
const ENTER: KeyframeAnimationOptions = { duration: 320, easing: 'cubic-bezier(0, 0, 0.2, 1)', fill: 'backwards' };
const ENTER_AFTER_LEAVE = 60; // leaving chips set off first, then the new ones come out
const PULLED = 'scale(0.3)';

/** The chips React renders; ghosts (chips on their way out) carry no data-tag. */
function chipsOf(host: HTMLElement): HTMLElement[] {
  return [...host.querySelectorAll<HTMLElement>(':scope > [data-tag]')];
}

function layoutBox(el: HTMLElement): Box {
  return { x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight };
}

/** Where a chip is on screen now, running animations included, in the host's content coordinates. */
function visualBox(el: HTMLElement, host: HTMLElement, hostRect: DOMRect): Box {
  const rect = el.getBoundingClientRect();
  const w = el.offsetWidth;
  const h = el.offsetHeight;
  const cx = rect.left + rect.width / 2 - hostRect.left - host.clientLeft + host.scrollLeft;
  const cy = rect.top + rect.height / 2 - hostRect.top - host.clientTop + host.scrollTop;
  return { x: cx - w / 2, y: cy - h / 2, w, h };
}

function toward(box: Box, cx: number, cy: number): string {
  return `translate(${cx - box.x - box.w / 2}px, ${cy - box.y - box.h / 2}px) ${PULLED}`;
}

function stop(el: HTMLElement) {
  for (const animation of el.getAnimations()) animation.cancel();
}

function reducedMotion(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Moves the chips of a tag cloud when the set of shown tags changes: chips that go are
 * pulled into the cloud's centre while they fade, chips that come grow out of it, the
 * rest glide to their new place, and the cloud's height follows.
 *
 * `key` names the shown tags. Call `capture()` right before a change made in the cloud
 * (a click, a keystroke); it notes where every chip is on screen, mid-animation included,
 * so a change during a running animation starts from there. Chips are the host's direct
 * children with a `data-tag` attribute; the host should be `relative isolate`.
 */
export function useCloudMotion<T extends HTMLElement>(key: string) {
  const hostRef = useRef<T>(null);
  const seen = useRef<Seen>({ key, host: null, chips: new Map(), height: 0 });
  const before = useRef<{ boxes: Map<string, Box>; height: number } | null>(null);
  const ghosts = useRef(new Map<string, HTMLElement>());

  const capture = useCallback(() => {
    const host = hostRef.current;
    if (!host) return;
    const hostRect = host.getBoundingClientRect();
    const boxes = new Map<string, Box>();
    for (const el of chipsOf(host)) boxes.set(el.dataset.tag ?? '', visualBox(el, host, hostRect));
    before.current = { boxes, height: hostRect.height };
  }, []);

  useLayoutEffect(() => {
    const host = hostRef.current;
    const prev = seen.current;
    const from = before.current;
    before.current = null;
    if (!host) {
      seen.current = { key, host: null, chips: new Map(), height: 0 };
      return;
    }
    const animate = prev.host === host && prev.key !== key && !reducedMotion() && typeof host.animate === 'function';
    if (animate) for (const animation of host.getAnimations()) animation.cancel();
    const chips = new Map<string, { box: Box; el: HTMLElement }>();
    for (const el of chipsOf(host)) chips.set(el.dataset.tag ?? '', { box: layoutBox(el), el });
    const height = host.offsetHeight;
    seen.current = { key, host, chips, height };
    if (!animate) return;

    const start = (tag: string, fallback: Box) => from?.boxes.get(tag) ?? fallback;
    const cx = host.scrollLeft + host.clientWidth / 2;
    const cy = host.scrollTop + host.clientHeight / 2;
    let leaving = 0;
    for (const [tag, { box, el }] of prev.chips) {
      if (chips.has(tag) || el.isConnected) continue;
      const at = start(tag, box);
      stop(el);
      el.removeAttribute('data-tag');
      el.setAttribute('aria-hidden', 'true');
      el.tabIndex = -1;
      Object.assign(el.style, {
        position: 'absolute',
        left: `${at.x}px`,
        top: `${at.y}px`,
        width: `${at.w}px`,
        margin: '0',
        pointerEvents: 'none',
        zIndex: '-1', // behind the chips that stay; the host isolates, so not behind the popover
      });
      host.appendChild(el);
      ghosts.current.get(tag)?.remove();
      ghosts.current.set(tag, el);
      const animation = el.animate([{ transform: 'none', opacity: 1 }, { transform: toward(at, cx, cy), opacity: 0 }], LEAVE);
      animation.onfinish = () => {
        el.remove();
        if (ghosts.current.get(tag) === el) ghosts.current.delete(tag);
      };
      leaving += 1;
    }
    for (const [tag, { box, el }] of chips) {
      const old = prev.chips.get(tag);
      if (!old) {
        ghosts.current.get(tag)?.remove();
        ghosts.current.delete(tag);
        el.animate([{ transform: toward(box, cx, cy), opacity: 0 }, { transform: 'none', opacity: 1 }], {
          ...ENTER,
          delay: leaving ? ENTER_AFTER_LEAVE : 0,
        });
        continue;
      }
      const at = start(tag, old.box);
      const dx = at.x - box.x;
      const dy = at.y - box.y;
      if (Math.abs(dx) + Math.abs(dy) < 0.5) continue;
      stop(el);
      el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }], MOVE);
    }
    const startHeight = from?.height ?? prev.height;
    if (Math.abs(startHeight - height) > 1) {
      // Clip while the height eases, so chips flying in or out never raise a scrollbar.
      host.style.overflow = 'hidden';
      const animation = host.animate(
        [
          { flexBasis: 'auto', height: `${startHeight}px` },
          { flexBasis: 'auto', height: `${height}px` },
        ],
        MOVE,
      );
      animation.onfinish = () => {
        if (!host.getAnimations().length) host.style.overflow = '';
      };
      animation.oncancel = animation.onfinish;
    }
  });

  return { hostRef, capture };
}
