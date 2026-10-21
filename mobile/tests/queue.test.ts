/// <reference types="node" />
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { ApiError, type Upload } from '../src/api/types.ts';
import { type Job, type NewJob, summarize, type UploadClient, UploadQueue } from '../src/uploads/queue.ts';

const CHUNK = 4;

/** A pretend PC with the same rules as app/services/uploads.py: chunks in order, repeats ignored. */
class FakePc implements UploadClient {
  uploads = new Map<string, Upload & { space: string; parent: string }>();
  completed: string[] = [];
  failNext: ApiError[] = [];
  chunkCalls = 0;
  private n = 0;

  private maybeFail() {
    const e = this.failNext.shift();
    if (e) throw e;
  }

  async startUpload(space: string, parent: string, name: string, size: number) {
    this.maybeFail();
    const u = { id: `u${++this.n}`, name, size, received: 0, chunk_size: CHUNK, status: 'in_progress' as const, item_id: null, space, parent };
    this.uploads.set(u.id, u);
    return { ...u };
  }

  async uploadStatus(id: string) {
    this.maybeFail();
    const u = this.uploads.get(id);
    if (!u) throw new ApiError(404, 'NOT_FOUND', 'Upload not found.');
    return { ...u };
  }

  async sendChunk(id: string, index: number, slice: { offset: number; length: number }) {
    this.chunkCalls++;
    this.maybeFail();
    const u = this.uploads.get(id)!;
    const offset = index * CHUNK;
    assert.equal(slice.offset, offset);
    if (offset + slice.length <= u.received) return { ...u };
    if (offset !== u.received) throw new ApiError(409, 'OUT_OF_ORDER', 'Chunks must be sent in order.');
    u.received = offset + slice.length;
    return { ...u };
  }

  async completeUpload(id: string) {
    this.maybeFail();
    const u = this.uploads.get(id)!;
    if (u.received !== u.size) throw new ApiError(400, 'INCOMPLETE_UPLOAD', 'Not all of the file has arrived yet.');
    (u as { status: string }).status = 'completed';
    this.completed.push(u.name);
    return { id: 'item-' + id, kind: 'file' as const, name: u.name, size: u.size, created_at: 0, modified_at: 0,
             created_by_name: 'sam', mine: true, can_modify: true, child_count: null };
  }

  async cancelUpload(id: string) {
    this.uploads.delete(id);
    return { ok: true };
  }
}

function setup(opts: { saved?: Job[]; client?: FakePc; files?: Set<string> } = {}) {
  const pc = opts.client ?? new FakePc();
  const files = opts.files ?? new Set(['a', 'b', 'c', 'd', 'e']);
  let clock = 1_000;
  const saves: Job[][] = [];
  const timers: { fn: () => void; at: number }[] = [];
  const signedOut: string[] = [];
  const queue = new UploadQueue({
    load: async () => opts.saved ?? [],
    save: async (jobs) => void saves.push(jobs),
    clientFor: (id) => (id === 'pc1' ? pc : null),
    fileExists: (uri) => files.has(uri),
    removeFile: (uri) => void files.delete(uri),
    now: () => clock,
    setTimer: (fn, ms) => {
      const t = { fn, at: clock + ms };
      timers.push(t);
      return t;
    },
    clearTimer: (t) => {
      const i = timers.indexOf(t as (typeof timers)[number]);
      if (i >= 0) timers.splice(i, 1);
    },
    onSignedOut: (id) => void signedOut.push(id),
  });
  const advance = async (ms: number) => {
    clock += ms;
    for (const t of timers.filter((t) => t.at <= clock)) {
      timers.splice(timers.indexOf(t), 1);
      t.fn();
    }
    await settle();
  };
  return { queue, pc, files, saves, advance, signedOut };
}

const settle = () => new Promise((r) => setTimeout(r, 20));

function job(uri: string, size: number, serverId = 'pc1'): NewJob {
  return { serverId, spaceId: 's1', parentId: 'root', folderLabel: 'My files', name: `${uri}.HEIC`, uri, size };
}

test('sends every chunk in order, completes, and removes the phone copy', async () => {
  const { queue, pc, files } = setup();
  await queue.add([job('a', 10)]);
  await settle();
  const [j] = queue.getSnapshot();
  assert.equal(j.status, 'done');
  assert.equal(j.sent, 10);
  assert.deepEqual(pc.completed, ['a.HEIC']);
  assert.equal(pc.chunkCalls, 3); // 4 + 4 + 2 bytes
  assert.ok(!files.has('a'));
});

test('an empty file still completes', async () => {
  const { queue, pc } = setup();
  await queue.add([job('a', 0)]);
  await settle();
  assert.equal(queue.getSnapshot()[0].status, 'done');
  assert.deepEqual(pc.completed, ['a.HEIC']);
});

test('never sends more than three files at once', async () => {
  const pc = new FakePc();
  let inFlight = 0;
  let most = 0;
  const original = pc.sendChunk.bind(pc);
  pc.sendChunk = async (...args) => {
    inFlight++;
    most = Math.max(most, inFlight);
    await new Promise((r) => setTimeout(r, 5));
    inFlight--;
    return original(...args);
  };
  const { queue } = setup({ client: pc });
  await queue.add(['a', 'b', 'c', 'd', 'e'].map((u) => job(u, 8)));
  await new Promise((r) => setTimeout(r, 150));
  assert.equal(most, 3);
  assert.ok(queue.getSnapshot().every((j) => j.status === 'done'));
});

test('a dropped connection waits, then resumes from what the PC already has', async () => {
  const { queue, pc, advance } = setup();
  pc.failNext = [];
  const original = pc.sendChunk.bind(pc);
  let calls = 0;
  pc.sendChunk = async (...args) => {
    calls++;
    if (calls === 2) throw new ApiError(0, 'NETWORK', "Can't reach your PC.");
    return original(...args);
  };
  await queue.add([job('a', 12)]);
  await settle();
  let [j] = queue.getSnapshot();
  assert.equal(j.status, 'waiting');
  assert.equal(j.sent, 4);
  assert.match(j.error!, /reach/);
  await advance(2_000); // first back-off
  [j] = queue.getSnapshot();
  assert.equal(j.status, 'done');
  assert.equal(pc.uploads.size, 1, 'resumed the same upload instead of starting over');
});

test('after the app is closed mid-upload it carries on with the same PC upload', async () => {
  const pc = new FakePc();
  const started = await pc.startUpload('s1', 'root', 'a.HEIC', 10);
  await pc.sendChunk(started.id, 0, { offset: 0, length: 4 });
  const saved: Job = { ...job('a', 10), id: 'j1', uploadId: started.id, sent: 4, status: 'sending', error: null, attempts: 0,
                       retryAt: 0, addedAt: 1 };
  const { queue } = setup({ saved: [saved], client: pc });
  await queue.ready();
  await settle();
  assert.equal(queue.getSnapshot()[0].status, 'done');
  assert.equal(pc.chunkCalls, 3); // the one before closing, then the remaining two
});

test('an expired upload on the PC starts over cleanly', async () => {
  const pc = new FakePc();
  const saved: Job = { ...job('a', 6), id: 'j1', uploadId: 'gone', sent: 4, status: 'waiting', error: null, attempts: 0,
                       retryAt: 0, addedAt: 1 };
  const { queue } = setup({ saved: [saved], client: pc });
  await queue.ready();
  await settle();
  const [j] = queue.getSnapshot();
  assert.equal(j.status, 'done');
  assert.notEqual(j.uploadId, 'gone');
});

test("problems that won't fix themselves fail with the PC's message", async () => {
  const { queue, pc, files } = setup();
  pc.failNext = [new ApiError(413, 'QUOTA_EXCEEDED', "Not enough space left in this folder's quota.")];
  await queue.add([job('a', 10)]);
  await settle();
  const [j] = queue.getSnapshot();
  assert.equal(j.status, 'failed');
  assert.match(j.error!, /quota/);
  assert.ok(!files.has('a'));
  assert.equal(summarize(queue.getSnapshot()).failed, 1);
});

test('uploads paused on the PC wait and try again', async () => {
  const { queue, pc, advance } = setup();
  pc.failNext = [new ApiError(503, 'UPLOADS_PAUSED', 'Uploads are paused by the administrator.')];
  await queue.add([job('a', 4)]);
  await settle();
  assert.equal(queue.getSnapshot()[0].status, 'waiting');
  await advance(29_000);
  assert.equal(queue.getSnapshot()[0].status, 'waiting');
  await advance(1_000);
  assert.equal(queue.getSnapshot()[0].status, 'done');
});

test('a signed-out PC keeps the uploads and asks to sign in', async () => {
  const { queue, pc, signedOut } = setup();
  pc.failNext = [new ApiError(401, 'UNAUTHENTICATED', 'Please sign in.')];
  await queue.add([job('a', 4)]);
  await settle();
  assert.equal(queue.getSnapshot()[0].status, 'waiting');
  assert.deepEqual(signedOut, ['pc1']);
  queue.resume(); // what signing in again does
  await settle();
  assert.equal(queue.getSnapshot()[0].status, 'done');
});

test('uploads for another PC wait until that PC is the current one', async () => {
  const { queue, pc } = setup();
  await queue.add([job('a', 4, 'pc2')]);
  await settle();
  assert.equal(queue.getSnapshot()[0].status, 'waiting');
  assert.equal(pc.chunkCalls, 0);
});

test('cancel stops sending, tells the PC, and removes the phone copy', async () => {
  const pc = new FakePc();
  const original = pc.sendChunk.bind(pc);
  pc.sendChunk = async (...args) => {
    await new Promise((r) => setTimeout(r, 10));
    return original(...args);
  };
  const { queue, files } = setup({ client: pc });
  const [added] = await queue.add([job('a', 40)]);
  await new Promise((r) => setTimeout(r, 15));
  await queue.cancel(added.id);
  await new Promise((r) => setTimeout(r, 40));
  const [j] = queue.getSnapshot();
  assert.equal(j.status, 'cancelled');
  assert.equal(pc.uploads.size, 0);
  assert.ok(pc.chunkCalls < 10);
  assert.ok(!files.has('a'));
});

test('a file that disappeared from the phone fails clearly; retry and clear work', async () => {
  const files = new Set<string>();
  const { queue } = setup({ files });
  const [added] = await queue.add([job('a', 4)]);
  await settle();
  assert.match(queue.getSnapshot()[0].error!, /no longer on this phone/);
  files.add('a');
  queue.retry(added.id);
  await settle();
  assert.equal(queue.getSnapshot()[0].status, 'done');
  queue.clearFinished();
  assert.equal(queue.getSnapshot().length, 0);
});

test('progress adds up across files', () => {
  const base = { ...job('a', 10), id: 'x', uploadId: null, error: null, attempts: 0, retryAt: 0, addedAt: 0 };
  const s = summarize([
    { ...base, status: 'sending', sent: 5 },
    { ...base, status: 'waiting', sent: 0, size: 30 },
    { ...base, status: 'done', sent: 10 },
  ]);
  assert.equal(s.active, 2);
  assert.equal(s.done, 1);
  assert.equal(s.progress, 5 / 40);
});

test('after an upload, the preview hook gets the new item while the phone copy still exists', async () => {
  const pc = new FakePc();
  const files = new Set(['a']);
  const seen: string[] = [];
  const queue = new UploadQueue({
    load: async () => [],
    save: async () => undefined,
    clientFor: () => pc,
    fileExists: (uri) => files.has(uri),
    removeFile: (uri) => void files.delete(uri),
    onUploaded: async (j, item) => {
      seen.push(`${item.name}:${files.has(j.uri)}`);
      throw new Error('preview failed'); // never fails the upload
    },
  });
  await queue.add([job('a', 6)]);
  await settle();
  assert.deepEqual(seen, ['a.HEIC:true']);
  assert.equal(queue.getSnapshot()[0].status, 'done');
  assert.ok(!files.has('a'));
});
