import { useEffect, useRef } from 'react';
import { useReactFlow } from '@xyflow/react';

/** Fit once the pane has a real size and after nodes have been measured. */
export function useFitGraph(key: string, nodeCount: number) {
  const { fitView } = useReactFlow();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || nodeCount === 0) return;
    let stop = false;
    const run = () => {
      if (stop) return;
      if (el.clientWidth < 24 || el.clientHeight < 24) return;
      void fitView({ padding: 0.2, duration: 0 });
    };
    run();
    const frame = window.requestAnimationFrame(run);
    const ro = new ResizeObserver(run);
    ro.observe(el);
    const later = window.setTimeout(() => {
      run();
      ro.disconnect();
    }, 200);
    return () => {
      stop = true;
      window.cancelAnimationFrame(frame);
      ro.disconnect();
      window.clearTimeout(later);
    };
  }, [fitView, key, nodeCount]);

  return ref;
}
