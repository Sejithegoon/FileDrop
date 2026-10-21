// How requests reach a PC: the real one through the pinned native module, or the built-in demo PC.
import { WifidropNet } from '@modules/wifidrop-net';

import { ApiError } from './types';

export type Reply = { status: number; body: string };

export interface Transport {
  send(method: string, path: string, headers: Record<string, string>, body?: string): Promise<Reply>;
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

  async send(method: string, path: string, headers: Record<string, string>, body?: string): Promise<Reply> {
    if (!WifidropNet) throw new ApiError(0, 'NO_NATIVE', 'This build of the app can only run the demo.');
    try {
      const r = await WifidropNet.request({ url: this.base + path, method, headers, body, pin: this.pin });
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

export function errorFrom(r: Reply): ApiError {
  try {
    const e = JSON.parse(r.body).error;
    if (e?.code) return new ApiError(r.status, e.code, e.message ?? 'Something went wrong.');
  } catch {
    // not JSON
  }
  return new ApiError(r.status, 'HTTP_' + r.status, `Your PC answered with an error (${r.status}).`);
}
