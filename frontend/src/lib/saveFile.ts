import { getChromeHost } from '@/lib/chromeHost';

export class ExportCancelled extends Error {
  constructor() {
    super('cancelled');
    this.name = 'ExportCancelled';
  }
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  const size = 0x8000;
  for (let index = 0; index < bytes.length; index += size) {
    binary += String.fromCharCode(...bytes.subarray(index, index + size));
  }
  return btoa(binary);
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

type SavePicker = (options: {
  suggestedName?: string;
  types?: Array<{ description?: string; accept: Record<string, string[]> }>;
}) => Promise<{ createWritable: () => Promise<{ write: (data: Blob) => Promise<void>; close: () => Promise<void> }> }>;

/** Ask where to store an export. False means the user closed the dialog. */
export async function saveExportFile(filename: string, blob: Blob): Promise<boolean> {
  const kind = filename.toLowerCase().endsWith('.zip') ? 'zip' : 'json';
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const host = getChromeHost();
  if (host?.saveFile) {
    const content = kind === 'json' ? new TextDecoder().decode(bytes) : bytesToBase64(bytes);
    const saved = await host.saveFile(filename, content, kind);
    return Boolean(saved);
  }
  const picker = (window as Window & { showSaveFilePicker?: SavePicker }).showSaveFilePicker;
  if (picker) {
    try {
      const handle = await picker({
        suggestedName: filename,
        types: [
          kind === 'json'
            ? { description: 'JSON', accept: { 'application/json': ['.json'] } }
            : { description: 'ZIP', accept: { 'application/zip': ['.zip'] } },
        ],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return true;
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return false;
      if (!(error instanceof DOMException) || error.name !== 'NotAllowedError') throw error;
    }
  }
  downloadBlob(filename, blob);
  return true;
}
