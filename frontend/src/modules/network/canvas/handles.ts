import type { PortDef } from '@/modules/network/model/document';

export function rfHandleId(port: PortDef): string {
  if (port.direction === 'out' && port.id === 'message') return 'out-message';
  return port.id;
}

export function docHandleId(handle: string | null | undefined): string {
  if (handle === 'out-message') return 'message';
  return handle ?? '';
}
