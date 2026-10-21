import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/utils';

/** Text column: content width, never wider than 250px, ellipsis when the pane is narrower. */
export const COL_TEXT = 'minmax(0,250px)';
/** Short column: one line at content width, still capped at 250px. */
export const COL_FIT = 'max-content';

export function HistoryGrid({ columns, children }: { columns: string; children: ReactNode }) {
  return (
    <div className="w-full overflow-x-auto">
      <div
        role="table"
        className="grid w-max text-sm"
        // This max-content grid leaks its height to the document past overflow:hidden. Paint containment stops that.
        style={{ gridTemplateColumns: columns, contain: 'paint' }}
      >
        {children}
      </div>
    </div>
  );
}

export function HistoryRow({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="row"
      className={cn(
        'col-span-full grid grid-cols-subgrid items-center border-b hover:bg-muted/50 data-[state=selected]:bg-muted',
        className,
      )}
      {...props}
    />
  );
}

export const historyHeadClass =
  'flex h-10 min-w-0 max-w-[250px] items-center overflow-hidden text-ellipsis whitespace-nowrap px-3 text-left text-xs font-medium text-muted-foreground';

export const historyCellClass = 'min-w-0 max-w-[250px] overflow-hidden text-ellipsis whitespace-nowrap px-3 py-2';
