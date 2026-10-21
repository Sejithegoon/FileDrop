// The WiFiDrop PC's /api/v1, as the app uses it.
import { errorFrom, type Transport } from './transport';
import type { Info, Item, Listing, Me, Space } from './types';
import { ApiError } from './types';

/** The newest PC API this app understands, and the oldest it still works with. */
export const APP_API = 1;

export class Client {
  constructor(
    private readonly transport: Transport,
    private token: string | null = null,
  ) {}

  private headers(json: boolean): Record<string, string> {
    const h: Record<string, string> = { 'X-WiFiDrop': '1', Accept: 'application/json' };
    if (json) h['Content-Type'] = 'application/json';
    if (this.token) h.Authorization = `Bearer ${this.token}`;
    return h;
  }

  private async call<T>(method: string, path: string, body?: unknown): Promise<T> {
    const r = await this.transport.send(method, '/api/v1' + path, this.headers(body !== undefined),
      body === undefined ? undefined : JSON.stringify(body));
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

  download(item: Item, destination: string) {
    return this.transport.download(item.id, `/api/v1/download/${encodeURIComponent(item.id)}`, this.headers(false), destination);
  }
}
