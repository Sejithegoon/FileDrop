// WiFiDrop PCs announcing themselves on this Wi-Fi (the PC advertises _wifidrop._tcp).
import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';

import { WifidropNet } from '@modules/wifidrop-net';

export type FoundPc = { name: string; serverId: string; host: string; port: number };

/** The service name is "WiFiDrop on <PC name>"; show just the PC name. */
export function pcNameFrom(serviceName: string): string {
  return serviceName.replace(/^WiFiDrop on /, '') || serviceName;
}

export function useDiscovery(): { found: FoundPc[]; available: boolean; error: string | null } {
  const [found, setFound] = useState<FoundPc[]>([]);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      const net = WifidropNet;
      if (!net) return;
      const subs = [
        net.addListener('onServiceFound', ({ name, txt }) => {
          const port = Number(txt.port);
          if (!txt.id || !txt.ip || !port || txt.https !== '1') return; // HTTPS is needed to pair securely
          const pc = { name: pcNameFrom(name), serverId: txt.id, host: txt.ip, port };
          setFound((list) => [...list.filter((p) => p.serverId !== pc.serverId), pc]);
        }),
        net.addListener('onServiceLost', ({ name }) => {
          setFound((list) => list.filter((p) => p.name !== pcNameFrom(name)));
        }),
        net.addListener('onDiscoveryError', () => {
          setError('Turn on Local Network access for WiFiDrop in Settings to find your PC automatically.');
        }),
      ];
      net.startDiscovery();
      return () => {
        net.stopDiscovery();
        subs.forEach((s) => s.remove());
      };
    }, []),
  );

  return { found, available: !!WifidropNet, error };
}
