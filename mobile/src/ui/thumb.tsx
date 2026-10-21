// Thumbnails: fetched from the PC through the app's own connection (so they work with the pinned key),
// kept in the phone's cache, and swapped in for the file-type icon once they arrive.
import { Ionicons } from '@expo/vector-icons';
import { File, Paths } from 'expo-file-system';
import { Image } from 'expo-image';
import { useEffect, useState } from 'react';
import { Platform, View, type ViewStyle } from 'react-native';

import type { Client } from '@/api/client';
import type { Item } from '@/api/types';
import { fileKind, KIND_ICONS } from '@/lib/format';
import { usePrefs } from '@/state/prefs';
import { useSession } from '@/state/session';
import { noPreview as none, previewFiles as ready } from '@/state/thumbcache';

import type { IconName } from './kit';
import { useColors } from './theme';

const waiting: (() => void)[] = [];
let active = 0;
const MAX_AT_ONCE = 4;

function slot(): Promise<() => void> {
  return new Promise((resolve) => {
    const go = () => {
      active++;
      resolve(() => {
        active--;
        waiting.shift()?.();
      });
    };
    if (active < MAX_AT_ONCE) go();
    else waiting.push(go);
  });
}

async function fetchThumb(client: Client, serverId: string, item: Item): Promise<string | null> {
  const key = `${serverId}:${item.id}:${item.modified_at}`;
  if (none.has(key)) return null;
  const cached = ready.get(key);
  if (cached) return cached;
  const file = new File(Paths.cache, 'thumbs', serverId, `${item.id}-${item.modified_at}.jpg`);
  if (file.exists && file.size > 0) {
    ready.set(key, file.uri);
    return file.uri;
  }
  const release = await slot();
  try {
    const { uri } = await client.thumb(item.id, file.uri);
    ready.set(key, uri);
    return uri;
  } catch {
    none.add(key);
    return null;
  } finally {
    release();
  }
}

export function canHaveThumb(item: Item) {
  if (item.kind !== 'file') return false;
  const kind = fileKind(item.name);
  return kind === 'image' || kind === 'video';
}

export function Thumb({ item, size = 44, radius = 10, style }: { item: Item; size?: number; radius?: number; style?: ViewStyle }) {
  const c = useColors();
  const { client, pc } = useSession();
  const { previews } = usePrefs();
  const [uri, setUri] = useState<string | null>(null);
  const kind = fileKind(item.name, item.kind === 'folder');
  // The web preview (demo only) has no file system to cache thumbnails in.
  const want = Platform.OS !== 'web' && previews && !!client && !!pc && canHaveThumb(item);

  useEffect(() => {
    let live = true;
    if (want) fetchThumb(client!, pc!.serverId, item).then((u) => live && setUri(u));
    return () => {
      live = false;
    };
  }, [want, client, pc, item]);

  const iconColor = c[kind === 'file' ? 'doc' : kind];
  return (
    <View style={[{ width: size, height: size, borderRadius: radius, overflow: 'hidden', alignItems: 'center', justifyContent: 'center',
                    backgroundColor: kind === 'folder' ? 'transparent' : c.surface2 }, style]}>
      {want && uri ? (
        <>
          <Image source={{ uri }} style={{ width: size, height: size }} contentFit="cover" transition={150} accessibilityIgnoresInvertColors />
          {kind === 'video' && (
            <View style={{ position: 'absolute', right: 3, bottom: 3, backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: 8, padding: 2 }}>
              <Ionicons name="play" size={Math.max(10, size / 5)} color="#fff" />
            </View>
          )}
        </>
      ) : (
        <Ionicons name={KIND_ICONS[kind] as IconName} size={size * (kind === 'folder' ? 0.72 : 0.55)} color={iconColor} />
      )}
    </View>
  );
}
