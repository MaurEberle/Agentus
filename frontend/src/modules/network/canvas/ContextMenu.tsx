import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

export type MenuState =
  | { kind: 'pane'; x: number; y: number; flow: { x: number; y: number } }
  | { kind: 'node'; x: number; y: number; id: string }
  | { kind: 'edge'; x: number; y: number; id: string };

export function CanvasContextMenu({
  menu,
  onClose,
  onInsert,
  onFit,
  onDuplicate,
  onDelete,
}: {
  menu: MenuState;
  onClose: () => void;
  onInsert: (flow: { x: number; y: number }) => void;
  onFit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();

  useEffect(() => {
    const close = () => onClose();
    window.addEventListener('click', close);
    window.addEventListener('scroll', close, true);
    return () => {
      window.removeEventListener('click', close);
      window.removeEventListener('scroll', close, true);
    };
  }, [onClose]);

  return (
    <div
      role="menu"
      className="fixed z-50 min-w-40 rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
      style={{ left: menu.x, top: menu.y }}
      onClick={(event) => event.stopPropagation()}
    >
      {menu.kind === 'pane' ? (
        <>
          <MenuItem onClick={() => onInsert(menu.flow)}>{t('network.context.insert')}</MenuItem>
          <MenuItem onClick={onFit}>{t('network.context.fit')}</MenuItem>
        </>
      ) : null}
      {menu.kind === 'node' ? (
        <>
          <MenuItem onClick={onDuplicate}>{t('network.context.duplicate')}</MenuItem>
          <MenuItem onClick={onDelete}>{t('network.context.delete')}</MenuItem>
        </>
      ) : null}
      {menu.kind === 'edge' ? (
        <MenuItem onClick={onDelete}>{t('network.context.delete')}</MenuItem>
      ) : null}
    </div>
  );
}

function MenuItem({ children, onClick }: { children: string; onClick: () => void }) {
  return (
    <Button type="button" variant="ghost" size="sm" className="w-full justify-start" onClick={onClick}>
      {children}
    </Button>
  );
}
