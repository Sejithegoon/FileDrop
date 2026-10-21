// Opening an item: folders open, photos and videos open in the viewer, anything else goes to the share sheet.
import { File, Paths } from 'expo-file-system';
import { router } from 'expo-router';
import * as Sharing from 'expo-sharing';
import { Platform } from 'react-native';

import type { Client } from '@/api/client';
import type { Item } from '@/api/types';
import { fileKind } from '@/lib/format';

export function viewable(item: Pick<Item, 'kind' | 'name'>) {
  if (item.kind !== 'file') return false;
  const kind = fileKind(item.name);
  return kind === 'image' || kind === 'video';
}

/** Brings the file to the phone (or reuses the copy from last time) and returns where it is. */
export async function fetchToPhone(client: Client, item: Pick<Item, 'id' | 'name' | 'size'>): Promise<string> {
  const file = new File(Paths.cache, 'downloads', item.id, item.name);
  if (file.exists && file.size === item.size) return file.uri;
  const { uri } = await client.download(item as Item, file.uri);
  return uri;
}

export async function shareFile(uri: string, name: string) {
  if (Platform.OS !== 'web' && (await Sharing.isAvailableAsync())) await Sharing.shareAsync(uri, { dialogTitle: name });
}

export function openItem(item: Item, spaceId: string, share: (item: Item) => void) {
  if (item.kind === 'folder') {
    router.push({ pathname: '/files/[space]', params: { space: spaceId, folder: item.id, title: item.name } });
  } else if (viewable(item)) {
    router.push({ pathname: '/view', params: { id: item.id, name: item.name, size: String(item.size) } });
  } else {
    share(item);
  }
}
