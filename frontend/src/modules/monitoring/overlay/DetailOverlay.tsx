import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useMediaQuery } from '@/hooks/useMediaQuery';

export function DetailOverlay({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const desktop = useMediaQuery('(min-width: 768px)');
  const closeLabel = t('monitoring.close');

  if (desktop) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent closeLabel={closeLabel} className="max-h-[min(80vh,1000px)] overflow-hidden">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh] pr-3">{children}</ScrollArea>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" closeLabel={closeLabel} className="max-h-[min(80vh,1000px)]">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
        </SheetHeader>
        <ScrollArea className="mt-3 max-h-[60vh] pr-2">{children}</ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
