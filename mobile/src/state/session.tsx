// Which PC the app is talking to, and who is signed in.
import * as Device from 'expo-device';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { Client } from '@/api/client';
import { DEMO_SERVER_ID, DemoTransport } from '@/api/demo';
import { PinnedTransport } from '@/api/transport';
import type { Me } from '@/api/types';
import { baseUrl } from '@/lib/pairing';

import * as store from './store';
import type { SavedPc } from './store';

export const DEMO_PC: SavedPc = { serverId: DEMO_SERVER_ID, name: 'Demo PC', host: 'demo', port: 0, pin: '', demo: true };

type Session = {
  ready: boolean;
  pcs: SavedPc[];
  pc: SavedPc | null;
  client: Client | null;
  me: Me | null;
  signedIn: boolean;
  /** Remember a PC (after scanning its QR code or confirming its code) and make it the current one. */
  pair(pc: SavedPc): Promise<void>;
  choose(serverId: string): Promise<void>;
  signIn(username: string, password: string): Promise<Me>;
  setMe(me: Me): void;
  signOut(): Promise<void>;
  forget(serverId: string): Promise<void>;
};

const SessionContext = createContext<Session | null>(null);

function clientFor(pc: SavedPc, token: string | null) {
  const transport = pc.demo ? demoTransport : new PinnedTransport(baseUrl(pc), pc.pin);
  return new Client(transport, token);
}

const demoTransport = new DemoTransport();

function deviceName() {
  return Device.deviceName || Device.modelName || 'a phone';
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [pcs, setPcs] = useState<SavedPc[]>([]);
  const [pc, setPc] = useState<SavedPc | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    (async () => {
      const saved = await store.loadPcs();
      const last = await store.lastPcId();
      const current = saved.find((p) => p.serverId === last) ?? saved[0] ?? null;
      setPcs(saved);
      setPc(current);
      if (current) setToken(await store.loadToken(current.serverId));
      setReady(true);
    })();
  }, []);

  const client = useMemo(() => (pc ? clientFor(pc, token) : null), [pc, token]);

  const pair = useCallback(async (next: SavedPc) => {
    const others = pcs.filter((p) => p.serverId !== next.serverId);
    const previous = pcs.find((p) => p.serverId === next.serverId);
    const merged = { ...previous, ...next };
    const list = [merged, ...others];
    if (!next.demo) await store.savePcs(list.filter((p) => !p.demo));
    await store.setLastPcId(next.serverId);
    // A different key means a reinstalled PC: its old sign-in is no use.
    const keepToken = previous && previous.pin === next.pin;
    if (!keepToken) await store.deleteToken(next.serverId);
    setPcs(list);
    setPc(merged);
    setToken(keepToken ? await store.loadToken(next.serverId) : null);
    setMe(null);
  }, [pcs]);

  const choose = useCallback(async (serverId: string) => {
    const next = pcs.find((p) => p.serverId === serverId);
    if (!next) return;
    await store.setLastPcId(serverId);
    setPc(next);
    setToken(await store.loadToken(serverId));
    setMe(null);
  }, [pcs]);

  const signIn = useCallback(async (username: string, password: string) => {
    if (!pc) throw new Error('No PC chosen');
    const fresh = clientFor(pc, null);
    const result = await fresh.login(username.trim(), password, deviceName());
    await store.saveToken(pc.serverId, result.token);
    const updated = { ...pc, username: username.trim() };
    const list = pcs.map((p) => (p.serverId === pc.serverId ? updated : p));
    await store.savePcs(list.filter((p) => !p.demo));
    setPcs(list);
    setPc(updated);
    setToken(result.token);
    setMe(result.me);
    return result.me;
  }, [pc, pcs]);

  const signOut = useCallback(async () => {
    if (!pc) return;
    try {
      await client?.logout();
    } catch {
      // Signed out on the phone even if the PC can't be reached; the PC forgets idle sessions by itself.
    }
    await store.deleteToken(pc.serverId);
    setToken(null);
    setMe(null);
  }, [pc, client]);

  const forget = useCallback(async (serverId: string) => {
    const target = pcs.find((p) => p.serverId === serverId);
    if (target && pc?.serverId === serverId && token) {
      try {
        await client?.logout();
      } catch {
        // see signOut
      }
    }
    await store.deleteToken(serverId);
    const list = pcs.filter((p) => p.serverId !== serverId);
    await store.savePcs(list.filter((p) => !p.demo));
    setPcs(list);
    if (pc?.serverId === serverId) {
      const next = list[0] ?? null;
      setPc(next);
      setToken(next ? await store.loadToken(next.serverId) : null);
      setMe(null);
      if (next) await store.setLastPcId(next.serverId);
    }
  }, [pcs, pc, token, client]);

  const value: Session = {
    ready, pcs, pc, client, me, signedIn: !!token, pair, choose, signIn, setMe, signOut, forget,
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const s = useContext(SessionContext);
  if (!s) throw new Error('useSession outside SessionProvider');
  return s;
}
