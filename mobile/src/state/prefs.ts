// App preferences (not secret): previews on or off, list or grid. Saved on the phone.
import { File, Paths } from 'expo-file-system';
import { useSyncExternalStore } from 'react';
import { Platform } from 'react-native';

export type Prefs = { previews: boolean; folderView: 'list' | 'grid' };

const DEFAULTS: Prefs = { previews: true, folderView: 'list' };
const web = Platform.OS === 'web';
const listeners = new Set<() => void>();

function load(): Prefs {
  try {
    const raw = web ? globalThis.localStorage?.getItem('prefs') : (() => {
      const f = new File(Paths.document, 'prefs.json');
      return f.exists ? f.textSync() : null;
    })();
    return { ...DEFAULTS, ...(raw ? JSON.parse(raw) : {}) };
  } catch {
    return DEFAULTS;
  }
}

let current: Prefs = load();

export function setPref<K extends keyof Prefs>(key: K, value: Prefs[K]) {
  current = { ...current, [key]: value };
  listeners.forEach((fn) => fn());
  try {
    const raw = JSON.stringify(current);
    if (web) globalThis.localStorage?.setItem('prefs', raw);
    else {
      const f = new File(Paths.document, 'prefs.json');
      if (!f.exists) f.create();
      f.write(raw);
    }
  } catch {
    // kept for this session
  }
}

export function usePrefs(): Prefs {
  return useSyncExternalStore(
    (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    () => current,
    () => current,
  );
}
