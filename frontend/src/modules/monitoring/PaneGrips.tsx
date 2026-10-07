import {
  useCallback,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react';
import { cn } from '@/lib/utils';
import {
  clampPaneHeight,
  clampPaneShare,
  loadPanes,
  PANE_MAX_H,
  PANE_MIN_H,
  savePanes,
  type MonitoringPanes,
} from '@/modules/monitoring/panes';

export function useMonitoringPanes() {
  const [panes, setPanes] = useState(loadPanes);

  const update = useCallback((patch: Partial<MonitoringPanes>) => {
    setPanes((prev) => {
      const next = {
        ...prev,
        ...patch,
        chatH: patch.chatH != null ? clampPaneHeight(patch.chatH) : prev.chatH,
        graphH: patch.graphH != null ? clampPaneHeight(patch.graphH) : prev.graphH,
        activityH: patch.activityH != null ? clampPaneHeight(patch.activityH) : prev.activityH,
        graphShare: patch.graphShare != null ? clampPaneShare(patch.graphShare) : prev.graphShare,
      };
      savePanes(next);
      return next;
    });
  }, []);

  return [panes, update] as const;
}

function startDrag(
  event: ReactPointerEvent<HTMLDivElement>,
  onMove: (ev: PointerEvent) => void,
  cursor: string,
) {
  event.preventDefault();
  event.stopPropagation();
  const target = event.currentTarget;
  target.setPointerCapture(event.pointerId);
  const previousCursor = document.body.style.cursor;
  const previousSelect = document.body.style.userSelect;
  document.body.style.cursor = cursor;
  document.body.style.userSelect = 'none';
  function move(ev: PointerEvent) {
    onMove(ev);
  }
  function up() {
    if (target.hasPointerCapture(event.pointerId)) {
      target.releasePointerCapture(event.pointerId);
    }
    document.body.style.cursor = previousCursor;
    document.body.style.userSelect = previousSelect;
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
  }
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
}

export function HeightGrip({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (next: number) => void;
}) {
  const origin = useRef({ y: 0, h: 0 });
  return (
    <div
      role="separator"
      aria-orientation="horizontal"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={PANE_MIN_H}
      aria-valuemax={PANE_MAX_H}
      className="flex h-3 shrink-0 cursor-ns-resize touch-none items-center justify-center rounded-sm hover:bg-muted/50"
      onPointerDown={(event) => {
        origin.current = { y: event.clientY, h: value };
        startDrag(
          event,
          (ev) => onChange(origin.current.h + ev.clientY - origin.current.y),
          'ns-resize',
        );
      }}
    >
      <span className="h-1 w-8 rounded-full bg-border" aria-hidden />
    </div>
  );
}

export function WidthGrip({
  label,
  share,
  onChange,
}: {
  label: string;
  share: number;
  onChange: (next: number) => void;
}) {
  const origin = useRef({ x: 0, share: 0, width: 1 });
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={Math.round(share * 100)}
      aria-valuemin={28}
      aria-valuemax={72}
      className="hidden w-4 shrink-0 cursor-col-resize touch-none items-center justify-center self-stretch rounded-sm hover:bg-muted/50 md:flex"
      onPointerDown={(event) => {
        const row = event.currentTarget.parentElement;
        origin.current = {
          x: event.clientX,
          share,
          width: Math.max(1, row?.clientWidth ?? 1),
        };
        startDrag(
          event,
          (ev) => {
            const dx = ev.clientX - origin.current.x;
            onChange(origin.current.share + dx / origin.current.width);
          },
          'col-resize',
        );
      }}
    >
      <span className="h-8 w-1 rounded-full bg-border" aria-hidden />
    </div>
  );
}

export function paneColStyle(share: number): CSSProperties {
  return {
    flexGrow: share,
    flexShrink: 1,
    flexBasis: 0,
  };
}

export function SplitRow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex w-full min-w-0 flex-col md:flex-row md:items-start', className)}>{children}</div>
  );
}
