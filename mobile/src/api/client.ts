// The WiFiDrop PC's /api/v1, as the app uses it.
// Only type imports from transport, so Node can load this file for the live tests.
import type { FileSlice, Transport } from './transport';
import type { Info, Item, Listing, Me, Space, Upload } from './types.ts';
import { ApiError, errorFrom } from './types.ts';

/** The newest PC API this app understands, and the oldest it still works with. */
export const APP_API = 1;

export class Client {
  private readonly transport: Transport;
  private token: string | null;

  constructor(transport: Transport, token: string | null = null) {
    this.transport = transport;
    this.token = token;
  }

  private headers(json: boolean): Record<string, string> {
    const h: Record<string, string> = { 'X-WiFiDrop': '1', Accept: 'application/json' };
    if (json) h['Content-Type'] = 'application/json';
    if (this.token) h.Authorization = `Bearer ${this.token}`;
    return h;
  }

  private async call<T>(method: string, path: string, body?: unknown): Promise<T> {
    const r = await this.transport.send(method, '/api/v1' + path, this.headers(body !== undefined),
      body === undefined ? undefined : JSON.stringify(body));
    return this.parse<T>(r);
  }

  private parse<T>(r: { status: number; body: string }): T {
    if (r.status >= 400) throw errorFrom(r);
    try {
      return JSON.parse(r.body) as T;
    } catch {
      throw new ApiError(r.status, 'BAD_REPLY', "That doesn't look like a WiFiDrop PC.");
    }
  }

  async info(): Promise<Info> {
    const info = await this.call<Info>('GET', '/info');
    if (info.app !== 'wifidrop') throw new ApiError(0, 'NOT_WIFIDROP', "That doesn't look like a WiFiDrop PC.");
    if (info.min_app_api > APP_API) {
      throw new ApiError(0, 'APP_TOO_OLD', 'Your PC has a newer WiFiDrop. Update this app from the App Store or Google Play.');
    }
    return info;
  }

  async login(username: string, password: string, device: string): Promise<{ me: Me; token: string }> {
    const r = await this.call<Me & { token?: string }>('POST', '/auth/login', { username, password, client: 'app', device });
    if (!r.token) throw new ApiError(0, 'PC_TOO_OLD', 'Update WiFiDrop on your PC to use the app (version 0.2 or newer).');
    this.token = r.token;
    const { token, ...me } = r;
    return { me, token };
  }

  me = () => this.call<Me>('GET', '/me');

  changePassword = (current: string, next: string) => this.call<Me>('POST', '/me/password', { current, new: next });

  async logout(): Promise<void> {
    try {
      await this.call('POST', '/auth/logout');
    } finally {
      this.token = null;
    }
  }

  spaces = async () => (await this.call<{ spaces: Space[] }>('GET', '/spaces')).spaces;

  listing = (spaceId: string, folderId = 'root') =>
    this.call<Listing>('GET', `/spaces/${encodeURIComponent(spaceId)}/items?folder=${encodeURIComponent(folderId)}`);

  changes = async () => (await this.call<{ version: number }>('GET', '/changes')).version;

  // ---- uploads: create, send 8 MB chunks in order (resending one is harmless), complete ----

  startUpload = (spaceId: string, parentId: string, name: string, size: number) =>
    this.call<Upload>('POST', '/uploads', { space_id: spaceId, parent_id: parentId, name, size });

  uploadStatus = (uploadId: string) => this.call<Upload>('GET', `/uploads/${encodeURIComponent(uploadId)}`);

  async sendChunk(uploadId: string, index: number, slice: FileSlice): Promise<Upload> {
    const headers = { ...this.headers(false), 'Content-Type': 'application/octet-stream' };
    const r = await this.transport.send('PUT', `/api/v1/uploads/${encodeURIComponent(uploadId)}/chunks/${index}`, headers, slice);
    return this.parse<Upload>(r);
  }

  completeUpload = (uploadId: string) => this.call<Item>('POST', `/uploads/${encodeURIComponent(uploadId)}/complete`, {});

  cancelUpload = (uploadId: string) => this.call<{ ok: boolean }>('DELETE', `/uploads/${encodeURIComponent(uploadId)}`);

  download(item: Item, destination: string) {
    return this.transport.download(item.id, `/api/v1/download/${encodeURIComponent(item.id)}`, this.headers(false), destination);
  }
}
