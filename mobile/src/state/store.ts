// Paired PCs and sign-in tokens, kept in the phone's secure storage (Keychain / Android Keystore).
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

export type SavedPc = {
  serverId: string;
  name: string;
  host: string;
  port: number;
  pin: string;
  username?: string;
  demo?: boolean;
};

// Readable after the first unlock, so auto-upload (later) can run while the phone is locked.
const OPTIONS: SecureStore.SecureStoreOptions = { keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK };

// The web build only runs the demo, and has no secure storage.
const web = Platform.OS === 'web';

async function get(key: string): Promise<string | null> {
  if (web) return globalThis.localStorage?.getItem(key) ?? null;
  return SecureStore.getItemAsync(key, OPTIONS);
}

async function set(key: string, value: string): Promise<void> {
  if (web) return globalThis.localStorage?.setItem(key, value);
  return SecureStore.setItemAsync(key, value, OPTIONS);
}

async function remove(key: string): Promise<void> {
  if (web) return globalThis.localStorage?.removeItem(key);
  return SecureStore.deleteItemAsync(key, OPTIONS);
}

export async function loadPcs(): Promise<SavedPc[]> {
  try {
    const raw = await get('pcs');
    return raw ? (JSON.parse(raw) as SavedPc[]) : [];
  } catch {
    return [];
  }
}

export async function savePcs(pcs: SavedPc[]): Promise<void> {
  await set('pcs', JSON.stringify(pcs));
}

export const lastPcId = () => get('last');
export const setLastPcId = (id: string) => set('last', id);

export const loadToken = (serverId: string) => get(`token.${serverId}`);
export const saveToken = (serverId: string, token: string) => set(`token.${serverId}`, token);
export const deleteToken = (serverId: string) => remove(`token.${serverId}`);
