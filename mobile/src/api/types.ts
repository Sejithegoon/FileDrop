// Shapes of the WiFiDrop PC's /api/v1 replies (see app/api/lan.py on the PC).

export type Info = { app: 'wifidrop'; api: number; min_app_api: number; version: string; name: string; server_id: string };

export type User = { id: string; username: string; display_name: string; role: string; must_change_password: boolean };

export type Me = {
  user: User;
  status: { uploads_paused: boolean; downloads_paused: boolean };
  version: string;
  edition?: 'free' | 'pro'; // missing on PCs older than 0.2
  features?: { auto_upload: boolean };
};

export type Space = {
  id: string;
  kind: 'private' | 'shared';
  name: string;
  level: string | null;
  quota_bytes: number | null;
  used_bytes: number;
  root_id: string;
};

export type Item = {
  id: string;
  kind: 'file' | 'folder';
  name: string;
  size: number;
  created_at: number;
  modified_at: number;
  created_by_name: string;
  mine: boolean;
  can_modify: boolean;
  child_count: number | null;
};

export type Listing = {
  space: { id: string; name: string; kind: Space['kind']; level: string; quota_bytes: number | null; used_bytes: number };
  folder_id: string;
  crumbs: { id: string; name: string }[];
  items: Item[];
  can_upload: boolean;
};

export type SearchResult = Item & {
  space: { id: string; name: string; kind: Space['kind'] };
  parent_id: string;
  path: string[]; // folders between the space's top and the item
};

export type Upload = {
  id: string;
  name: string;
  size: number;
  received: number;
  chunk_size: number;
  status: 'queued' | 'in_progress' | 'interrupted' | 'finalising' | 'completed' | 'cancelled' | 'failed';
  item_id: string | null;
};

/** What the app shows when something goes wrong; code is the PC's error code or one of the app's own. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/** The PC's error reply ({"error": {"code", "message"}}) as an ApiError. */
export function errorFrom(r: { status: number; body: string }): ApiError {
  try {
    const e = JSON.parse(r.body).error;
    if (e?.code) return new ApiError(r.status, e.code, e.message ?? 'Something went wrong.');
  } catch {
    // not JSON
  }
  return new ApiError(r.status, 'HTTP_' + r.status, `Your PC answered with an error (${r.status}).`);
}
