// "Send photos / files to this folder": pick, then queue. Shared by Home's quick buttons and folders.
import { useCallback } from 'react';
import { Alert } from 'react-native';

import { useSession } from '@/state/session';

import { pickFiles, pickPhotos, sendToPc } from '.';

export type Target = { spaceId: string; parentId: string; label: string };

export function useSendTo() {
  const { pc } = useSession();
  return useCallback(async (what: 'photos' | 'files', target: Target): Promise<number> => {
    if (!pc) return 0;
    const picked = what === 'photos' ? await pickPhotos() : await pickFiles();
    if (picked === 'denied') {
      Alert.alert('Photos access is off', 'To send photos and videos, allow WiFiDrop to access your photos in Settings.');
      return 0;
    }
    if (picked.length) await sendToPc(picked, { serverId: pc.serverId, ...target });
    return picked.length;
  }, [pc]);
}
