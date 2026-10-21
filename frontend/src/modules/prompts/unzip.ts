function findEocd(bytes: Uint8Array): number {
  const start = Math.max(0, bytes.length - 22 - 65535);
  for (let index = bytes.length - 22; index >= start; index -= 1) {
    if (bytes[index] === 0x50 && bytes[index + 1] === 0x4b && bytes[index + 2] === 0x05 && bytes[index + 3] === 0x06) {
      return index;
    }
  }
  return -1;
}

async function inflateRaw(payload: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([payload]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

export async function unzipTextFiles(buffer: ArrayBuffer): Promise<Array<{ name: string; text: string }>> {
  const bytes = new Uint8Array(buffer);
  const view = new DataView(buffer);
  const eocd = findEocd(bytes);
  if (eocd < 0) return [];
  const count = view.getUint16(eocd + 10, true);
  let cursor = view.getUint32(eocd + 16, true);
  const files: Array<{ name: string; text: string }> = [];
  for (let index = 0; index < count && cursor + 46 <= bytes.length; index += 1) {
    if (view.getUint32(cursor, true) !== 0x02014b50) break;
    const method = view.getUint16(cursor + 10, true);
    const compressed = view.getUint32(cursor + 20, true);
    const nameLength = view.getUint16(cursor + 28, true);
    const extraLength = view.getUint16(cursor + 30, true);
    const commentLength = view.getUint16(cursor + 32, true);
    const localOffset = view.getUint32(cursor + 42, true);
    const name = new TextDecoder().decode(bytes.subarray(cursor + 46, cursor + 46 + nameLength));
    cursor += 46 + nameLength + extraLength + commentLength;
    if (!name || name.endsWith('/')) continue;
    if (localOffset + 30 > bytes.length) continue;
    const localName = view.getUint16(localOffset + 26, true);
    const localExtra = view.getUint16(localOffset + 28, true);
    const dataStart = localOffset + 30 + localName + localExtra;
    const payload = bytes.subarray(dataStart, dataStart + compressed);
    let raw: Uint8Array | null = null;
    if (method === 0) raw = payload;
    else if (method === 8 && typeof DecompressionStream !== 'undefined') {
      try {
        raw = await inflateRaw(payload);
      } catch {
        raw = null;
      }
    }
    if (!raw) continue;
    files.push({ name, text: new TextDecoder().decode(raw) });
  }
  return files;
}
