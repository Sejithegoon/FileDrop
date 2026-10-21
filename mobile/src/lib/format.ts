// Sizes, dates and file-type icons, matching the PC's web page.

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}

export function formatWhen(ms: number, now = Date.now()): string {
  const d = new Date(ms);
  const days = Math.floor((now - ms) / 86_400_000);
  if (days < 1 && new Date(now).getDate() === d.getDate()) {
    return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  }
  if (days < 7) return d.toLocaleDateString(undefined, { weekday: 'short' });
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: days > 300 ? 'numeric' : undefined });
}

export type FileKind = 'folder' | 'image' | 'video' | 'audio' | 'doc' | 'archive' | 'file';

const KINDS: Record<string, FileKind> = {};
for (const e of ['jpg', 'jpeg', 'png', 'gif', 'heic', 'heif', 'webp', 'bmp', 'tif', 'tiff', 'dng', 'raw']) KINDS[e] = 'image';
for (const e of ['mov', 'mp4', 'm4v', 'avi', 'mkv', 'webm', '3gp']) KINDS[e] = 'video';
for (const e of ['mp3', 'm4a', 'wav', 'aac', 'flac', 'ogg']) KINDS[e] = 'audio';
for (const e of ['pdf', 'doc', 'docx', 'txt', 'rtf', 'xls', 'xlsx', 'csv', 'ppt', 'pptx', 'pages', 'numbers', 'key', 'md']) KINDS[e] = 'doc';
for (const e of ['zip', '7z', 'rar', 'tar', 'gz']) KINDS[e] = 'archive';

export function fileKind(name: string, isFolder = false): FileKind {
  if (isFolder) return 'folder';
  const ext = name.includes('.') ? name.split('.').pop()!.toLowerCase() : '';
  return KINDS[ext] ?? 'file';
}

export const KIND_ICONS: Record<FileKind, string> = {
  folder: 'folder',
  image: 'image',
  video: 'videocam',
  audio: 'musical-notes',
  doc: 'document-text',
  archive: 'archive',
  file: 'document',
};
