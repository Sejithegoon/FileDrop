// Keeps the screen awake while uploads run, and resumes them whenever the app comes back to the front.
import { activateKeepAwakeAsync, deactivateKeepAwake } from 'expo-keep-awake';
import { useEffect } from 'react';
import { AppState } from 'react-native';

import { queue, summarize, useUploads } from '.';

const TAG = 'wifidrop-uploads';

export function UploadKeeper() {
  const { active } = summarize(useUploads());

  useEffect(() => {
    if (!active) return;
    activateKeepAwakeAsync(TAG).catch(() => undefined);
    return () => {
      deactivateKeepAwake(TAG).catch(() => undefined);
    };
  }, [active]);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') queue.resume();
    });
    return () => sub.remove();
  }, []);

  return null;
}
