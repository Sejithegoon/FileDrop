/// <reference types="node" />
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { test } from 'node:test';

import { isPlainWiFiDropLink, parsePairingQr, pinCode, sha256 } from '../src/lib/pairing.ts';

const PIN = 'mixvENvXxc0b0p4Em6u9mBHok36vkh1JA8B-GM3tex8';

test('sha256 matches Node for many lengths', () => {
  for (const n of [0, 1, 55, 56, 63, 64, 65, 200]) {
    const data = new Uint8Array(n).map((_, i) => (i * 31 + 7) & 255);
    assert.equal(Buffer.from(sha256(data)).toString('hex'), createHash('sha256').update(data).digest('hex'));
  }
});

test('pairing code matches the PC (values from app.core.tls.pin_code)', () => {
  assert.equal(pinCode(PIN), 'QOPK-BASC');
  assert.equal(pinCode('abc'), 'XJ4B-NP4P');
});

test('reads the QR code the PC shows', () => {
  const p = parsePairingQr(`https://10.0.0.99:8443/?wd=1&pin=${PIN}&id=3ea76d0d1a068654f1f2`);
  assert.deepEqual(p, { host: '10.0.0.99', port: 8443, pin: PIN, serverId: '3ea76d0d1a068654f1f2' });
});

test('refuses anything that is not a WiFiDrop pairing code', () => {
  for (const text of [
    'https://10.0.0.99:8443/',
    `http://10.0.0.99:8443/?wd=1&pin=${PIN}&id=3ea76d0d1a068654f1f2`,
    `https://10.0.0.99:8443/?wd=1&pin=short&id=3ea76d0d1a068654f1f2`,
    `https://10.0.0.99:8443/?wd=1&pin=${PIN}&id=NOTHEX`,
    `https://10.0.0.99:99999/?wd=1&pin=${PIN}&id=3ea76d0d1a068654f1f2`,
    'hello',
  ]) {
    assert.equal(parsePairingQr(text), null, text);
  }
});

test('spots the plain web link of an older WiFiDrop', () => {
  assert.ok(isPlainWiFiDropLink('https://10.0.0.99:8443/'));
  assert.ok(!isPlainWiFiDropLink('https://example.com/page'));
});

test('reads the plain web link for Expo Go test mode', async () => {
  const { parsePlainLink } = await import('../src/lib/pairing.ts');
  assert.deepEqual(parsePlainLink('http://10.0.0.99:8443/'), { host: '10.0.0.99', port: 8443, secure: false });
  assert.deepEqual(parsePlainLink('https://10.0.0.99:8443/?wd=1&pin=x'), { host: '10.0.0.99', port: 8443, secure: true });
  assert.equal(parsePlainLink('http://10.0.0.99/'), null);
  assert.equal(parsePlainLink('hello'), null);
});
