// How requests reach a PC: the real one through the pinned native module, or the built-in demo PC.
import { WifidropNet } from '@modules/wifidrop-net';

import { ApiError, errorFrom } from './types';

export { errorFrom };

export type Reply = { status: number; body: string };

/** Part of a file on the phone, sent as a request body straight from disk (upload chunks). */
export type FileSlice = { uri: string; offset: number; length: number };

export interface Transport {
  send(method: string, path: string, headers: Record<string, string>, body?: string | FileSlice): Promise<Reply>;
  download(id: string, path: string, headers: Record<string, string>, destination: string): Promise<{ uri: string; bytes: number }>;
}

const NETWORK_MESSAGES: Record<string, string> = {
  PIN_MISMATCH: "This doesn't look like your PC: its security key changed. If you reinstalled WiFiDrop, pair again by scanning its QR code.",
  TIMEOUT: "Your PC didn't answer. Check that it's on, WiFiDrop's web server is running, and you're on the same Wi-Fi.",
  NETWORK: "Can't reach your PC. Check that it's on, WiFiDrop's web server is running, and you're on the same Wi-Fi.",
  OFFLINE: "Your phone isn't connected to Wi-Fi.",
};

export function networkError(e: unknown): ApiError {
  const code = (e as { code?: string })?.code ?? 'NETWORK';
  return new ApiError(0, code, NETWORK_MESSAGES[code] ?? NETWORK_MESSAGES.NETWORK);
}

export class PinnedTransport implements Transport {
  constructor(
    private readonly base: string,
    private readonly pin: string,
  ) {}

  async send(method: string, path: string, headers: Record<string, string>, body?: string | FileSlice): Promise<Reply> {
    if (!WifidropNet) throw new ApiError(0, 'NO_NATIVE', 'This build of the app can only run the demo.');
    const payload = typeof body === 'object'
      ? { bodyFile: body.uri, bodyOffset: body.offset, bodyLength: body.length, timeoutMs: 180_000 }
      : { body };
    try {
      const r = await WifidropNet.request({ url: this.base + path, method, headers, pin: this.pin, ...payload });
      return { status: r.status, body: r.body };
    } catch (e) {
      throw networkError(e);
    }
  }

  async download(id: string, path: string, headers: Record<string, string>, destination: string) {
    if (!WifidropNet) throw new ApiError(0, 'NO_NATIVE', 'This build of the app can only run the demo.');
    let r;
    try {
      r = await WifidropNet.download({ id, url: this.base + path, headers, destination, pin: this.pin });
    } catch (e) {
      throw networkError(e);
    }
    if (r.status >= 400 || !r.uri) throw errorFrom({ status: r.status, body: r.body ?? '' });
    return { uri: r.uri, bytes: r.bytes ?? 0 };
  }
}

