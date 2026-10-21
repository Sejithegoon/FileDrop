// A pretend WiFiDrop PC inside the app. Lets people (and App Store reviewers, who have no WiFiDrop PC)
// try the app, and lets the screens run in a web browser. Nothing leaves the phone.
import type { Reply, Transport } from './transport';
import type { Item, Me, Space } from './types';
import { ApiError } from './types';

export const DEMO_SERVER_ID = 'demo0000000000000000';
export const DEMO_USER = 'demo';
export const DEMO_PASSWORD = 'demo';

const DAY = 24 * 3600 * 1000;
const now = Date.now();

type Node = Item & { parent: string; space: string };

function node(id: string, space: string, parent: string, kind: Item['kind'], name: string, size = 0, daysAgo = 1, by = 'demo'): Node {
  const t = now - daysAgo * DAY;
  return { id, space, parent, kind, name, size, created_at: t, modified_at: t, created_by_name: by, mine: by === 'demo',
           can_modify: by === 'demo', child_count: null };
}

const SPACES: Space[] = [
  { id: 'sp-mine', kind: 'private', name: 'demo', level: 'owner', quota_bytes: null, used_bytes: 0, root_id: 'root-mine' },
  { id: 'sp-family', kind: 'shared', name: 'Family', level: 'contribute', quota_bytes: null, used_bytes: 0, root_id: 'root-family' },
  { id: 'sp-school', kind: 'shared', name: 'Group project', level: 'view', quota_bytes: null, used_bytes: 0, root_id: 'root-school' },
];

const NODES: Node[] = [
  node('f-photos', 'sp-mine', 'root-mine', 'folder', 'Photos', 0, 2),
  node('f-docs', 'sp-mine', 'root-mine', 'folder', 'Documents', 0, 9),
  node('i-1', 'sp-mine', 'f-photos', 'file', 'IMG_2041.HEIC', 2_412_330, 2),
  node('i-2', 'sp-mine', 'f-photos', 'file', 'IMG_2042.HEIC', 2_198_112, 2),
  node('i-3', 'sp-mine', 'f-photos', 'file', 'Beach.MOV', 84_220_416, 3),
  node('i-4', 'sp-mine', 'f-docs', 'file', 'Resume.pdf', 182_004, 9),
  node('i-5', 'sp-mine', 'root-mine', 'file', 'Notes.txt', 2_048, 1),
  node('f-trip', 'sp-family', 'root-family', 'folder', 'Summer trip', 0, 20, 'mom'),
  node('i-6', 'sp-family', 'f-trip', 'file', 'Lake.jpg', 3_401_920, 20, 'mom'),
  node('i-7', 'sp-family', 'root-family', 'file', 'Recipes.docx', 48_221, 30, 'dad'),
  node('i-8', 'sp-school', 'root-school', 'file', 'Slides.pptx', 5_220_104, 4, 'sam'),
  node('i-9', 'sp-school', 'root-school', 'file', 'Report draft.docx', 91_300, 5, 'alex'),
];

const ME: Me = {
  user: { id: 'u-demo', username: DEMO_USER, display_name: 'Demo', role: 'user', must_change_password: false },
  status: { uploads_paused: false, downloads_paused: false },
  version: 'demo',
  edition: 'pro',
  features: { auto_upload: true },
};

function json(status: number, body: unknown): Reply {
  return { status, body: JSON.stringify(body) };
}

function fail(status: number, code: string, message: string): Reply {
  return json(status, { error: { code, message } });
}

function rootName(rootId: string) {
  const space = SPACES.find((s) => s.root_id === rootId)!;
  return space.kind === 'private' ? 'My files' : space.name;
}

function crumbs(folderId: string) {
  const out: { id: string; name: string }[] = [];
  let id: string | undefined = folderId;
  while (id) {
    const n = NODES.find((x) => x.id === id);
    if (n) {
      out.unshift({ id: n.id, name: n.name });
      id = n.parent;
    } else {
      out.unshift({ id, name: rootName(id) });
      id = undefined;
    }
  }
  return out;
}

export class DemoTransport implements Transport {
  private signedIn = false;

  async send(method: string, path: string, headers: Record<string, string>, body?: string): Promise<Reply> {
    await new Promise((r) => setTimeout(r, 150)); // feel like a network
    const route = `${method} ${path.split('?')[0]}`;
    const query = new URLSearchParams(path.split('?')[1] ?? '');
    if (route === 'GET /api/v1/info') {
      return json(200, { app: 'wifidrop', api: 1, min_app_api: 1, version: 'demo', name: 'Demo PC', server_id: DEMO_SERVER_ID });
    }
    if (route === 'POST /api/v1/auth/login') {
      const { username, password } = JSON.parse(body ?? '{}');
      if (username?.toLowerCase() !== DEMO_USER || password !== DEMO_PASSWORD) {
        return fail(401, 'INVALID_LOGIN', 'Wrong username or password. In the demo, both are "demo".');
      }
      this.signedIn = true;
      return json(200, { ...ME, token: 'demo-token' });
    }
    if (!this.signedIn && headers.Authorization !== 'Bearer demo-token') return fail(401, 'UNAUTHENTICATED', 'Please sign in.');
    this.signedIn = true;
    if (route === 'POST /api/v1/auth/logout') {
      this.signedIn = false;
      return json(200, { ok: true });
    }
    if (route === 'GET /api/v1/me') return json(200, ME);
    if (route === 'GET /api/v1/changes') return json(200, { version: 1 });
    if (route === 'POST /api/v1/me/password') return fail(400, 'DEMO', "The demo's password can't be changed.");
    if (route === 'GET /api/v1/spaces') {
      return json(200, {
        spaces: SPACES.map((s) => ({ ...s, used_bytes: NODES.filter((n) => n.space === s.id).reduce((t, n) => t + n.size, 0) })),
      });
    }
    const listing = /^GET \/api\/v1\/spaces\/([^/]+)\/items$/.exec(route);
    if (listing) {
      const space = SPACES.find((s) => s.id === decodeURIComponent(listing[1]));
      if (!space) return fail(404, 'NOT_FOUND', 'Folder not found.');
      const folder = query.get('folder') === 'root' || !query.get('folder') ? space.root_id : query.get('folder')!;
      const items = NODES.filter((n) => n.parent === folder)
        .map(({ parent, space: _s, ...item }) => ({
          ...item,
          child_count: item.kind === 'folder' ? NODES.filter((c) => c.parent === item.id).length : null,
        }))
        .sort((a, b) => (a.kind === b.kind ? a.name.localeCompare(b.name) : a.kind === 'folder' ? -1 : 1));
      return json(200, {
        space: { id: space.id, name: space.name, kind: space.kind, level: space.level, quota_bytes: null, used_bytes: 0 },
        folder_id: folder, crumbs: crumbs(folder), items, can_upload: space.level !== 'view',
      });
    }
    return fail(404, 'NOT_FOUND', 'Not available in the demo.');
  }

  async download(id: string, _path: string, _headers: Record<string, string>, destination: string) {
    const item = NODES.find((n) => n.id === id);
    if (!item) throw new ApiError(404, 'NOT_FOUND', 'That item no longer exists.');
    // A tiny stand-in file: the demo has no real photos to hand out.
    const { File } = await import('expo-file-system');
    const file = new File(destination);
    file.parentDirectory.create({ intermediates: true, idempotent: true });
    file.create({ overwrite: true });
    file.write(`This is a demo file standing in for "${item.name}".\nConnect WiFiDrop to your PC to get your real files.\n`);
    return { uri: file.uri, bytes: file.size ?? 0 };
  }
}
