// Pairing with a WiFiDrop PC: reading its QR code and the short code shown in its admin window.
// No React Native imports here, so `npm test` runs it with plain Node.

export type Pairing = {
  host: string;
  port: number;
  pin: string; // base64url SHA-256 of the PC's public key
  serverId: string;
};

const PIN = /^[A-Za-z0-9_-]{43}$/;
const SERVER_ID = /^[0-9a-f]{20}$/;

/** The PC's QR code holds https://<ip>:<port>/?wd=1&pin=…&id=… ; anything else isn't a WiFiDrop pairing code. */
export function parsePairingQr(text: string): Pairing | null {
  const m = /^https:\/\/(\[[0-9a-fA-F:.]+\]|[A-Za-z0-9.-]+):(\d{1,5})\/?\?([^#]*)/.exec(text.trim());
  if (!m) return null;
  const query: Record<string, string> = {};
  for (const part of m[3].split('&')) {
    const [k, v = ''] = part.split('=');
    try {
      query[decodeURIComponent(k)] = decodeURIComponent(v.replace(/\+/g, ' '));
    } catch {
      return null;
    }
  }
  const port = Number(m[2]);
  if (query.wd !== '1' || !PIN.test(query.pin ?? '') || !SERVER_ID.test(query.id ?? '') || port < 1 || port > 65535) {
    return null;
  }
  return { host: m[1], port, pin: query.pin, serverId: query.id };
}

/** True when the text is the PC's plain web link (an older WiFiDrop, or plain HTTP) rather than an app pairing code. */
export function isPlainWiFiDropLink(text: string): boolean {
  return /^https?:\/\/[^/\s]+:\d+\/?$/.test(text.trim());
}

/** Same as the PC's tls.pin_code: first 8 base32 characters of SHA-256(pin), as XXXX-XXXX. */
export function pinCode(pin: string): string {
  const code = base32(sha256(new TextEncoder().encode(pin))).slice(0, 8);
  return `${code.slice(0, 4)}-${code.slice(4)}`;
}

export function baseUrl(p: { host: string; port: number; insecure?: boolean }): string {
  return `${p.insecure ? 'http' : 'https'}://${p.host}:${p.port}`;
}

/** host and port from a plain web link such as http://10.0.0.99:8443/ (Expo Go test mode). */
export function parsePlainLink(text: string): { host: string; port: number; secure: boolean } | null {
  const m = /^(https?):\/\/([A-Za-z0-9.-]+):(\d{1,5})(\/|\/?\?.*)?$/.exec(text.trim());
  if (!m) return null;
  const port = Number(m[3]);
  return port > 0 && port < 65536 ? { host: m[2], port, secure: m[1] === 'https' } : null;
}

// ---- small helpers -----------------------------------------------------------------------

const B32 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';

export function base32(bytes: Uint8Array): string {
  let out = '';
  let bits = 0;
  let value = 0;
  for (const b of bytes) {
    value = (value << 8) | b;
    bits += 8;
    while (bits >= 5) {
      out += B32[(value >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  if (bits > 0) out += B32[(value << (5 - bits)) & 31];
  return out;
}

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

/** SHA-256 (FIPS 180-4). Only used for short strings, so clarity beats speed. */
export function sha256(data: Uint8Array): Uint8Array {
  const length = data.length;
  const padded = new Uint8Array(((length + 9 + 63) >> 6) << 6);
  padded.set(data);
  padded[length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padded.length - 8, Math.floor(length / 0x20000000));
  view.setUint32(padded.length - 4, (length << 3) >>> 0);
  const h = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
  const w = new Uint32Array(64);
  const rotr = (x: number, n: number) => (x >>> n) | (x << (32 - n));
  for (let off = 0; off < padded.length; off += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(off + i * 4);
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, hh] = h;
    for (let i = 0; i < 64; i++) {
      const t1 = (hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) >>> 0;
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
      hh = g;
      g = f;
      f = e;
      e = (d + t1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (t1 + t2) >>> 0;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
  }
  const out = new Uint8Array(32);
  const outView = new DataView(out.buffer);
  for (let i = 0; i < 8; i++) outView.setUint32(i * 4, h[i]);
  return out;
}
