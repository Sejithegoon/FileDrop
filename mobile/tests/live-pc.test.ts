/// <reference types="node" />
// Runs the app's real API client and upload queue against a real WiFiDrop PC server.
// Skipped unless pointed at a test server (never your real one):
//   WIFIDROP_LIVE=https://<ip>:<port> WIFIDROP_LIVE_PIN=<pin> WIFIDROP_LIVE_USER=<user> WIFIDROP_LIVE_PASS=<pass> npm test
// The transport below stands in for the native module: it trusts only the pinned key, like the phone does.
import assert from 'node:assert/strict';
import { createHash, randomBytes, X509Certificate } from 'node:crypto';
import { mkdtempSync, openSync, readSync, closeSync, writeFileSync, existsSync, rmSync, readFileSync } from 'node:fs';
import https from 'node:https';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import type { TLSSocket } from 'node:tls';

import { Client } from '../src/api/client.ts';
import { ApiError } from '../src/api/types.ts';
import { UploadQueue } from '../src/uploads/queue.ts';

const BASE = process.env.WIFIDROP_LIVE;
const PIN = process.env.WIFIDROP_LIVE_PIN ?? '';
const skip = !BASE && 'set WIFIDROP_LIVE to run against a test PC server';

type Slice = { uri: string; offset: number; length: number };

function pinOf(socket: TLSSocket): string {
  const der = socket.getPeerCertificate(false).raw;
  if (!der) return '';
  const spki = new X509Certificate(der).publicKey.export({ type: 'spki', format: 'der' });
  return createHash('sha256').update(spki).digest('base64url');
}

class NodePinnedTransport {
  readonly base: string;
  readonly pin: string;

  constructor(base: string, pin: string) {
    this.base = base;
    this.pin = pin;
  }

  private request(method: string, path: string, headers: Record<string, string>, body?: Buffer, toFile?: string) {
    return new Promise<{ status: number; body: string }>((resolve, reject) => {
      const req = https.request(this.base + path, { method, headers, rejectUnauthorized: false, agent: false }, (res) => {
        const parts: Buffer[] = [];
        res.on('data', (d: Buffer) => parts.push(d));
        res.on('end', () => {
          const all = Buffer.concat(parts);
          if (toFile && (res.statusCode ?? 0) < 400) writeFileSync(toFile, all);
          resolve({ status: res.statusCode ?? 0, body: toFile ? '' : all.toString('utf8') });
        });
      });
      req.on('socket', (s: TLSSocket) => s.once('secureConnect', () => {
        if (pinOf(s) !== this.pin) req.destroy(Object.assign(new Error('pin mismatch'), { code: 'PIN_MISMATCH' }));
      }));
      req.on('error', (e: Error & { code?: string }) => reject(new ApiError(0, e.code === 'PIN_MISMATCH' ? 'PIN_MISMATCH' : 'NETWORK', e.message)));
      req.end(body);
    });
  }

  send(method: string, path: string, headers: Record<string, string>, body?: string | Slice) {
    let buf: Buffer | undefined;
    if (typeof body === 'string') buf = Buffer.from(body);
    else if (body) {
      buf = Buffer.alloc(body.length);
      const fd = openSync(body.uri, 'r');
      readSync(fd, buf, 0, body.length, body.offset);
      closeSync(fd);
    }
    return this.request(method, path, headers, buf);
  }

  async download(_id: string, path: string, headers: Record<string, string>, destination: string) {
    const r = await this.request('GET', path, headers, undefined, destination);
    if (r.status >= 400) throw new ApiError(r.status, 'HTTP_' + r.status, 'download failed');
    return { uri: destination, bytes: readFileSync(destination).length };
  }
}

test('pairing: the pinned key is accepted, any other key is refused', { skip }, async () => {
  const info = await new Client(new NodePinnedTransport(BASE!, PIN)).info();
  assert.equal(info.app, 'wifidrop');
  await assert.rejects(new Client(new NodePinnedTransport(BASE!, 'A'.repeat(43))).info(), (e: ApiError) => e.code === 'PIN_MISMATCH');
});

test('sign in, upload three files through the queue (one bigger than a chunk), download one back intact', { skip }, async () => {
  const transport = new NodePinnedTransport(BASE!, PIN);
  const client = new Client(transport);
  const { me } = await client.login(process.env.WIFIDROP_LIVE_USER!, process.env.WIFIDROP_LIVE_PASS!, 'Node test');
  assert.ok(me.user.username);
  const space = (await client.spaces()).find((s) => s.kind === 'private')!;
  const root = (await client.listing(space.id)).folder_id;

  const dir = mkdtempSync(join(tmpdir(), 'wifidrop-live-'));
  const run = Date.now().toString(36); // unique names: the PC keeps both copies when a name repeats
  const files = [
    { name: `IMG_${run}.HEIC`, data: randomBytes(20 * 1024 * 1024 + 123) }, // three chunks
    { name: `clip_${run}.MOV`, data: randomBytes(3 * 1024 * 1024) },
    { name: `empty_${run}.txt`, data: Buffer.alloc(0) },
  ].map((f) => {
    const uri = join(dir, f.name);
    writeFileSync(uri, f.data);
    return { ...f, uri, sha: createHash('sha256').update(f.data).digest('hex') };
  });

  const queue = new UploadQueue({
    load: async () => [],
    save: async () => undefined,
    clientFor: () => client,
    fileExists: (uri) => existsSync(uri),
    removeFile: (uri) => rmSync(uri, { force: true }),
  });
  await queue.add(files.map((f) => ({ serverId: 'live', spaceId: space.id, parentId: root, folderLabel: 'My files',
                                      name: f.name, uri: f.uri, size: f.data.length })));
  for (let i = 0; i < 600 && queue.getSnapshot().some((j) => j.status === 'waiting' || j.status === 'sending'); i++) {
    await new Promise((r) => setTimeout(r, 100));
  }
  const jobs = queue.getSnapshot();
  assert.deepEqual(jobs.map((j) => [j.name, j.status, j.error]), files.map((f) => [f.name, 'done', null]));
  assert.ok(files.every((f) => !existsSync(f.uri)), 'phone copies removed after sending');

  const listed = (await client.listing(space.id)).items;
  for (const f of files) assert.equal(listed.find((i) => i.name === f.name)?.size, f.data.length, f.name);
  const big = listed.find((i) => i.name === files[0].name)!;
  const back = join(dir, 'back.HEIC');
  await client.download(big, back);
  assert.equal(createHash('sha256').update(readFileSync(back)).digest('hex'), files[0].sha, 'downloaded file matches');
  rmSync(dir, { recursive: true, force: true });
});
