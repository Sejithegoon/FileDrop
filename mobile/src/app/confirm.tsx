import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';

import { WifidropNet } from '@modules/wifidrop-net';

import { networkError } from '@/api/transport';
import type { Info } from '@/api/types';
import { baseUrl, pinCode } from '@/lib/pairing';
import { useSession } from '@/state/session';
import { Body, Button, Card, Loading, Notice, Screen, Title } from '@/ui/kit';
import { useColors } from '@/ui/theme';

/**
 * Pairing with a PC found on the Wi-Fi, without its QR code. Anyone on the network could announce a
 * fake PC, so the person checks the short code against the one WiFiDrop shows on the PC's screen.
 */
export default function Confirm() {
  const c = useColors();
  const { pair } = useSession();
  const params = useLocalSearchParams<{ name: string; host: string; port: string; serverId: string }>();
  const [pin, setPin] = useState<string | null>(null);
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await WifidropNet!.probe(`${baseUrl({ host: params.host, port: Number(params.port) })}/api/v1/info`);
        const body = JSON.parse(r.body) as Info;
        if (body.app !== 'wifidrop' || body.server_id !== params.serverId) throw new Error('mismatch');
        setPin(r.pin);
        setInfo(body);
      } catch (e) {
        setError(e instanceof Error && e.message === 'mismatch'
          ? "That PC didn't answer like a WiFiDrop PC. Scan its QR code instead."
          : networkError(e).message);
      }
    })();
  }, [params.host, params.port, params.serverId]);

  async function confirm() {
    if (!pin || !info) return;
    await pair({ serverId: info.server_id, name: info.name, host: params.host, port: Number(params.port), pin });
    router.dismissTo('/sign-in');
  }

  if (error) {
    return (
      <Screen>
        <Notice text={error} />
        <Button title="Scan QR code instead" icon="qr-code" onPress={() => router.replace('/scan')} />
      </Screen>
    );
  }
  if (!pin) return <Loading />;

  return (
    <Screen>
      <Title>Is this your PC?</Title>
      <Body>
        On <Text style={{ fontWeight: '700' }}>{params.name}</Text>, open WiFiDrop's Dashboard. Under the web link it shows a
        "WiFiDrop phone app code". It must match this one:
      </Body>
      <Card style={{ padding: 24, alignItems: 'center' }}>
        <Text accessibilityLabel={`Code ${pinCode(pin).split('').join(' ')}`} style={{ color: c.text, fontSize: 40, fontWeight: '700', letterSpacing: 4, fontVariant: ['tabular-nums'] }}>
          {pinCode(pin)}
        </Text>
      </Card>
      <View style={{ gap: 12 }}>
        <Button title="The codes match" icon="checkmark" onPress={confirm} />
        <Button title="They don't match" kind="secondary" onPress={() => router.back()} />
      </View>
      <Body muted>
        If they don't match, something else on this Wi-Fi is pretending to be your PC. Don't connect; scan the QR code on your PC instead.
      </Body>
    </Screen>
  );
}
