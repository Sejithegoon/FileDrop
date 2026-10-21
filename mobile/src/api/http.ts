// Expo Go test mode: plain HTTP to a PC with WiFiDrop's HTTPS turned off. Expo Go can't load the app's own
// native code (pinned HTTPS), so this lets the screens, uploads and downloads be tried on a phone before a
// real build exists. Not encrypted, so it's only offered inside Expo Go, and only on your own Wi-Fi.
import { File } from 'expo-file-system';

import { type FileSlice, networkError, type Reply, type Transport } from './transport';
import { ApiError } from './types';

function readSlice(slice: FileSlice): Uint8Array {
  const handle = new File(slice.uri).open();
  try {
    handle.offset = slice.offset;
    const out = new Uint8Array(slice.length);
    let filled = 0;
    while (filled < slice.length) {
      const part = handle.readBytes(slice.length - filled);
      if (part.length === 0) break;
      out.set(part, filled);
      filled += part.length;
    }
    return filled === slice.length ? out : out.slice(0, filled);
  } finally {
    handle.close();
  }
}

export class HttpTransport implements Transport {
  private readonly base: string;

  constructor(base: string) {
    this.base = base;
  }

  async send(method: string, path: string, headers: Record<string, string>, body?: string | FileSlice): Promise<Reply> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), typeof body === 'object' ? 180_000 : 30_000);
    try {
      const payload = typeof body === 'object' ? readSlice(body) : body;
      const res = await fetch(this.base + path, { method, headers, body: payload as BodyInit | undefined, signal: controller.signal });
      return { status: res.status, body: await res.text() };
    } catch (e) {
      throw networkError((e as Error)?.name === 'AbortError' ? { code: 'TIMEOUT' } : e);
    } finally {
      clearTimeout(timer);
    }
  }

  async download(_id: string, path: string, headers: Record<string, string>, destination: string) {
    const dest = new File(destination);
    dest.parentDirectory.create({ intermediates: true, idempotent: true });
    try {
      const file = await File.downloadFileAsync(this.base + path, dest, { headers, idempotent: true });
      return { uri: file.uri, bytes: file.size };
    } catch (e) {
      throw new ApiError(0, 'NETWORK', (e as Error)?.message || "Couldn't download the file.");
    }
  }
}
