import { modelHover, modelLabel } from '@/lib/modelName';
import { cn } from '@/lib/utils';

export function ModelName({
  value,
  variant = 'plain',
  className,
}: {
  value: string;
  /** `tag` puts the publisher behind the name. `plain` keeps it for the hover title. */
  variant?: 'plain' | 'tag';
  className?: string;
}) {
  const label = modelLabel(value);
  if (variant === 'tag' && label.publisher) {
    return (
      <span className={cn('inline-flex min-w-0 max-w-full items-center gap-1.5', className)} title={label.raw}>
        <span className="min-w-0 truncate">{label.name}</span>
        <span className="shrink-0 rounded border bg-muted px-1.5 py-0.5 font-sans text-[10px] font-normal leading-none text-muted-foreground">
          {label.publisher}
        </span>
      </span>
    );
  }
  return (
    <span className={cn('min-w-0 truncate', className)} title={modelHover(label)}>
      {label.name}
    </span>
  );
}
