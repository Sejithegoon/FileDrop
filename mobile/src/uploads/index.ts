// Phone side of the upload queue: pickers, the outbox folder, saving the queue, and the shared instance.
import { Directory, File, Paths } from 'expo-file-system';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { useSyncExternalStore } from 'react';
import { Platform } from 'react-native';

import { type Job, type UploadClient, UploadQueue } from './queue';

export { summarize, type Job } from './queue';

const web = Platform.OS === 'web';

let clientFor: (serverId: string) => UploadClient | null = () => null;
let signedOut: (serverId: string) => void = () => undefined;

/** The session tells the queue which PC it can talk to right now. */
export function configureUploads(opts: { clientFor: typeof clientFor; onSignedOut: typeof signedOut }) {
  clientFor = opts.clientFor;
  signedOut = opts.onSignedOut;
  queue.resume();
}

// Picked files are moved here so the system can't clear them (as it may with caches) before they're sent.
function outbox() {
  const dir = new Directory(Paths.document, 'outbox');
  if (!dir.exists) dir.create({ intermediates: true, idempotent: true });
  return dir;
}

function queueFile() {
  return new File(Paths.document, 'uploads.json');
}

export const queue = new UploadQueue({
  async load() {
    try {
      if (web) return JSON.parse(globalThis.localStorage?.getItem('uploads') ?? '[]') as Job[];
      const f = queueFile();
      return f.exists ? (JSON.parse(await f.text()) as Job[]) : [];
    } catch {
      return [];
    }
  },
  async save(jobs) {
    const keep = jobs.filter((j) => j.status !== 'done' || Date.now() - j.addedAt < 24 * 3600 * 1000);
    if (web) return globalThis.localStorage?.setItem('uploads', JSON.stringify(keep));
    const f = queueFile();
    if (!f.exists) f.create();
    f.write(JSON.stringify(keep));
  },
  clientFor: (id) => clientFor(id),
  fileExists: (uri) => web || new File(uri).exists,
  removeFile(uri) {
    if (web) return;
    try {
      const f = new File(uri);
      const dir = f.parentDirectory;
      if (f.exists) f.delete();
      if (dir.uri.startsWith(outbox().uri) && dir.exists && dir.list().length === 0) dir.delete();
    } catch {
      // already gone
    }
  },
  onSignedOut: (id) => signedOut(id),
});

export function useUploads(): readonly Job[] {
  return useSyncExternalStore(queue.subscribe, queue.getSnapshot, queue.getSnapshot);
}

// ---- picking -----------------------------------------------------------------------------

export type Picked = { uri: string; name: string; size: number };

function nameFrom(uri: string, fallback: string) {
  const last = decodeURIComponent(uri.split('?')[0].split('/').pop() ?? '');
  return last || fallback;
}

function sizeOf(uri: string, known?: number | null) {
  if (known) return known;
  try {
    return new File(uri).size ?? 0;
  } catch {
    return 0;
  }
}

/**
 * Photos and videos as they are in the library (HEIC, HEVC), with no "preparing" conversion step.
 * iOS needs photo access to hand over originals, so ask first (once).
 */
export async function pickPhotos(): Promise<Picked[] | 'denied'> {
  if (!web) {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted && perm.accessPrivileges !== 'limited') return 'denied';
  }
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images', 'videos'],
    allowsMultipleSelection: true,
    selectionLimit: 0,
    preferredAssetRepresentationMode: ImagePicker.UIImagePickerPreferredAssetRepresentationMode.Current,
    quality: 1,
    exif: false,
  });
  if (result.canceled) return [];
  return result.assets.map((a, i) => ({
    uri: a.uri,
    name: a.fileName || nameFrom(a.uri, `${a.type === 'video' ? 'VID' : 'IMG'}_${Date.now()}_${i}`),
    size: sizeOf(a.uri, a.fileSize),
  }));
}

/** Any file from the Files app / Downloads. */
export async function pickFiles(): Promise<Picked[]> {
  const result = await DocumentPicker.getDocumentAsync({ multiple: true, copyToCacheDirectory: true, type: '*/*' });
  if (result.canceled) return [];
  return result.assets.map((a) => ({ uri: a.uri, name: a.name, size: sizeOf(a.uri, a.size) }));
}

/** Moves the picked files into the outbox and queues them for a folder on the PC. */
export async function sendToPc(picked: Picked[], target: { serverId: string; spaceId: string; parentId: string; label: string }) {
  const jobs = picked.map((p, i) => {
    let uri = p.uri;
    if (!web) {
      try {
        const dir = new Directory(outbox(), `${Date.now().toString(36)}-${i}`);
        dir.create({ intermediates: true, idempotent: true });
        const file = new File(p.uri);
        const dest = new File(dir, p.name.replace(/[/\\]/g, '_'));
        file.moveSync(dest);
        uri = file.uri;
      } catch {
        uri = p.uri; // send from where the picker left it
      }
    }
    return { serverId: target.serverId, spaceId: target.spaceId, parentId: target.parentId, folderLabel: target.label,
             name: p.name, uri, size: p.size };
  });
  return queue.add(jobs);
}
