// The upload queue: sends files to the PC in 8 MB chunks, three files at a time, and picks up where it
// left off after a dropped connection, a locked phone or a closed app (the PC remembers how much arrived).
// No React Native imports, so `npm test` exercises it with plain Node.
import { ApiError } from '../api/types.ts';
import type { Item, Upload } from '../api/types.ts';

export type JobStatus = 'waiting' | 'sending' | 'done' | 'failed' | 'cancelled';

export type Job = {
  id: string;
  serverId: string; // which PC
  spaceId: string;
  parentId: string; // folder id on the PC
  folderLabel: string; // shown in the list, e.g. "My files › Photos"
  name: string;
  uri: string; // the file on the phone (the app's own copy)
  size: number;
  uploadId: string | null; // the PC's upload, once started
  sent: number;
  status: JobStatus;
  error: string | null;
  attempts: number;
  retryAt: number;
  addedAt: number;
};

export type NewJob = Pick<Job, 'serverId' | 'spaceId' | 'parentId' | 'folderLabel' | 'name' | 'uri' | 'size'>;

/** The part of the API client the queue needs. */
export interface UploadClient {
  startUpload(spaceId: string, parentId: string, name: string, size: number): Promise<Upload>;
  uploadStatus(uploadId: string): Promise<Upload>;
  sendChunk(uploadId: string, index: number, slice: { uri: string; offset: number; length: number }): Promise<Upload>;
  completeUpload(uploadId: string): Promise<Item>;
  cancelUpload(uploadId: string): Promise<unknown>;
}

export type QueueDeps = {
  load(): Promise<Job[]>;
  save(jobs: Job[]): Promise<void>;
  /** The signed-in client for that PC, or null when it isn't the current PC or nobody is signed in. */
  clientFor(serverId: string): UploadClient | null;
  fileExists(uri: string): boolean;
  removeFile(uri: string): void;
  now?: () => number;
  setTimer?: (fn: () => void, ms: number) => unknown;
  clearTimer?: (t: unknown) => void;
  onSignedOut?(serverId: string): void;
  onFinished?(job: Job): void;
};

export const MAX_PARALLEL = 3;
const BACKOFF_MS = [2_000, 5_000, 15_000, 30_000, 60_000];
const SAVE_EVERY_MS = 1_000;

// PC errors that won't get better by trying again.
const FINAL = new Set(['FORBIDDEN', 'NOT_FOUND', 'TARGET_GONE', 'QUOTA_EXCEEDED', 'FILE_TOO_LARGE', 'INVALID_NAME',
  'INVALID_SIZE', 'INSUFFICIENT_STORAGE', 'NOT_A_FOLDER', 'STORAGE_NOT_SET']);
// Errors about the PC's upload record: start a fresh upload.
const RESTART = new Set(['UPLOAD_EXPIRED', 'UPLOAD_CANCELLED', 'UPLOAD_FINISHED']);

export class UploadQueue {
  private jobs: Job[] = [];
  private running = new Set<string>();
  private listeners = new Set<() => void>();
  private snapshot: readonly Job[] = [];
  private timer: unknown = null;
  private lastSave = 0;
  private saveTimer: unknown = null;
  private loaded: Promise<void>;
  private idCounter = 0;

  private readonly deps: QueueDeps;

  constructor(deps: QueueDeps) {
    this.deps = deps;
    this.loaded = deps.load().then((saved) => {
      // Anything mid-send when the app closed simply continues.
      this.jobs = saved.map((j) => (j.status === 'sending' ? { ...j, status: 'waiting', retryAt: 0 } : j));
      this.changed(true);
      this.kick();
    }).catch(() => undefined);
  }

  private now() {
    return (this.deps.now ?? Date.now)();
  }

  // ---- reading -------------------------------------------------------------------------

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  getSnapshot = () => this.snapshot;

  ready() {
    return this.loaded;
  }

  // ---- actions -------------------------------------------------------------------------

  async add(items: NewJob[]): Promise<Job[]> {
    await this.loaded;
    const now = this.now();
    const added = items.map((n) => ({
      ...n, id: `${now.toString(36)}-${(this.idCounter++).toString(36)}`, uploadId: null, sent: 0, status: 'waiting' as const,
      error: null, attempts: 0, retryAt: 0, addedAt: now,
    }));
    this.jobs = [...this.jobs, ...added];
    this.changed(true);
    this.kick();
    return added;
  }

  async cancel(id: string) {
    const job = this.find(id);
    if (!job || job.status === 'done' || job.status === 'cancelled') return;
    this.update(id, { status: 'cancelled', error: null }, true);
    this.deps.removeFile(job.uri);
    const client = this.deps.clientFor(job.serverId);
    if (job.uploadId && client) client.cancelUpload(job.uploadId).catch(() => undefined);
  }

  retry(id: string) {
    const job = this.find(id);
    if (!job || job.status !== 'failed') return;
    this.update(id, { status: 'waiting', error: null, attempts: 0, retryAt: 0 }, true);
    this.kick();
  }

  /** Forget finished and cancelled uploads (failed ones stay until retried or cancelled). */
  clearFinished() {
    this.jobs = this.jobs.filter((j) => j.status !== 'done' && j.status !== 'cancelled');
    this.changed(true);
  }

  /** Try every waiting upload now: after signing in, or coming back to the app. */
  resume = () => {
    this.jobs = this.jobs.map((j) => (j.status === 'waiting' ? { ...j, retryAt: 0 } : j));
    this.changed(false);
    this.kick();
  };

  kick = () => {
    if (this.timer !== null) {
      (this.deps.clearTimer ?? clearTimeout)(this.timer as ReturnType<typeof setTimeout>);
      this.timer = null;
    }
    const now = this.now();
    for (const job of this.jobs) {
      if (this.running.size >= MAX_PARALLEL) break;
      if (job.status !== 'waiting' || this.running.has(job.id) || job.retryAt > now) continue;
      const client = this.deps.clientFor(job.serverId);
      if (!client) continue;
      this.running.add(job.id);
      this.send(job.id, client).finally(() => {
        this.running.delete(job.id);
        this.kick();
      });
    }
    // Wake up for the next retry.
    const next = Math.min(...this.jobs.filter((j) => j.status === 'waiting' && j.retryAt > now).map((j) => j.retryAt));
    if (Number.isFinite(next)) {
      this.timer = (this.deps.setTimer ?? setTimeout)(() => {
        this.timer = null;
        this.kick();
      }, Math.max(50, next - now));
    }
  };

  // ---- sending -------------------------------------------------------------------------

  private async send(id: string, client: UploadClient) {
    let job = this.find(id)!;
    if (!this.deps.fileExists(job.uri)) {
      this.update(id, { status: 'failed', error: 'The file is no longer on this phone. Pick it again.' }, true);
      return;
    }
    this.update(id, { status: 'sending', error: null }, true);
    try {
      let info: Upload | null = null;
      if (job.uploadId) {
        try {
          info = await client.uploadStatus(job.uploadId);
          if (info.status === 'cancelled' || info.status === 'failed') info = null;
        } catch (e) {
          if (!(e instanceof ApiError) || (e.status !== 404 && e.status !== 410)) throw e;
        }
      }
      if (!info) {
        info = await client.startUpload(job.spaceId, job.parentId, job.name, job.size);
        this.update(id, { uploadId: info.id, sent: 0 }, true);
      }
      job = this.find(id)!;
      if (info.status !== 'completed') {
        let received = info.received;
        const chunk = info.chunk_size;
        while (received < job.size) {
          if (this.find(id)?.status !== 'sending') return; // cancelled meanwhile
          const index = Math.floor(received / chunk);
          const offset = index * chunk;
          const reply = await client.sendChunk(job.uploadId!, index, { uri: job.uri, offset, length: Math.min(chunk, job.size - offset) });
          received = reply.received;
          this.update(id, { sent: received, attempts: 0 });
        }
        if (this.find(id)?.status !== 'sending') return;
        await client.completeUpload(job.uploadId!);
      }
      this.update(id, { status: 'done', sent: job.size, error: null }, true);
      this.deps.removeFile(job.uri);
      this.deps.onFinished?.(this.find(id)!);
    } catch (e) {
      if (this.find(id)?.status !== 'sending') return;
      this.failed(id, e);
    }
  }

  private failed(id: string, e: unknown) {
    const job = this.find(id)!;
    const err = e instanceof ApiError ? e : new ApiError(0, 'NETWORK', 'Something went wrong. Retrying…');
    if (err.status === 401) {
      // Waits for resume(), which signing in calls.
      this.update(id, { status: 'waiting', error: 'Sign in again to continue.', retryAt: this.now() + 10 * 60_000 }, true);
      this.deps.onSignedOut?.(job.serverId);
      return;
    }
    if (RESTART.has(err.code)) {
      this.update(id, { status: 'waiting', uploadId: null, sent: 0, retryAt: this.now() }, true);
      return;
    }
    if (FINAL.has(err.code) || (err.status >= 400 && err.status < 500 && err.code !== 'OUT_OF_ORDER' && err.code !== 'INCOMPLETE_CHUNK'
        && err.code !== 'INCOMPLETE_UPLOAD' && err.code !== 'RATE_LIMITED')) {
      this.update(id, { status: 'failed', error: err.message }, true);
      this.deps.removeFile(job.uri);
      return;
    }
    // Network trouble, a paused PC or a hiccup: wait a bit longer each time, and keep going.
    const attempts = job.attempts + 1;
    const wait = err.code === 'UPLOADS_PAUSED' ? 30_000 : BACKOFF_MS[Math.min(attempts - 1, BACKOFF_MS.length - 1)];
    this.update(id, { status: 'waiting', attempts, retryAt: this.now() + wait, error: err.message }, true);
  }

  // ---- bookkeeping ---------------------------------------------------------------------

  private find(id: string) {
    return this.jobs.find((j) => j.id === id);
  }

  private update(id: string, patch: Partial<Job>, saveNow = false) {
    this.jobs = this.jobs.map((j) => (j.id === id ? { ...j, ...patch } : j));
    this.changed(saveNow);
  }

  private changed(saveNow: boolean) {
    this.snapshot = this.jobs;
    this.listeners.forEach((fn) => fn());
    const now = this.now();
    if (saveNow || now - this.lastSave >= SAVE_EVERY_MS) {
      this.lastSave = now;
      this.deps.save(this.jobs).catch(() => undefined);
    } else if (this.saveTimer === null) {
      this.saveTimer = (this.deps.setTimer ?? setTimeout)(() => {
        this.saveTimer = null;
        this.lastSave = this.now();
        this.deps.save(this.jobs).catch(() => undefined);
      }, SAVE_EVERY_MS);
    }
  }
}

/** Totals for the progress bar and the badge. */
export function summarize(jobs: readonly Job[]) {
  const active = jobs.filter((j) => j.status === 'waiting' || j.status === 'sending');
  const total = active.reduce((t, j) => t + j.size, 0);
  const sent = active.reduce((t, j) => t + j.sent, 0);
  return {
    active: active.length,
    failed: jobs.filter((j) => j.status === 'failed').length,
    done: jobs.filter((j) => j.status === 'done').length,
    progress: total ? sent / total : 0,
  };
}
