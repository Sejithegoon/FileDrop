import { router, useFocusEffect } from 'expo-router';
import { useCallback, useRef } from 'react';
import { AppState } from 'react-native';

import type { Client } from '@/api/client';
import { ApiError } from '@/api/types';

import { useSession } from './session';

/** Turns an error into a message, sending the person to sign in or pick a password when that's the problem. */
export function useErrorHandler() {
  const { signOut } = useSession();
  return useCallback(async (e: unknown): Promise<string | null> => {
    if (e instanceof ApiError) {
      if (e.status === 401) {
        await signOut();
        router.replace('/sign-in');
        return null;
      }
      if (e.code === 'PASSWORD_CHANGE_REQUIRED') {
        router.replace('/password');
        return null;
      }
      return e.message;
    }
    return 'Something went wrong. Try again.';
  }, [signOut]);
}

/**
 * Loads the screen each time it comes into view; then, while it's open and the app is in front, asks the PC
 * every few seconds whether anything changed (same as the web page) and reloads when it did.
 */
export function useLiveUpdates(client: Client | null, reload: () => void, everyMs = 3000) {
  const version = useRef<number | null>(null);
  useFocusEffect(
    useCallback(() => {
      if (!client) return;
      reload();
      let stopped = false;
      const tick = async () => {
        if (stopped || AppState.currentState !== 'active') return;
        try {
          const v = await client.changes();
          if (version.current !== null && v !== version.current) reload();
          version.current = v;
        } catch {
          // offline for a moment: the screen shows errors from its own loads
        }
      };
      tick();
      const timer = setInterval(tick, everyMs);
      return () => {
        stopped = true;
        clearInterval(timer);
      };
    }, [client, reload, everyMs]),
  );
}
