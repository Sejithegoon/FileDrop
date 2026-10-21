import { router } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Platform, Text, View } from 'react-native';

import { ApiError } from '@/api/types';
import { parsePlainLink } from '@/lib/pairing';
import { useDiscovery } from '@/state/discovery';
import { DEMO_PC, useSession } from '@/state/session';
import { HTTPS_OFF_HINT, testModePc } from '@/state/testmode';
import { Body, Button, Card, Field, Notice, Row, Screen, Separator, Title } from '@/ui/kit';
import { useColors } from '@/ui/theme';

export default function Connect() {
  const c = useColors();
  const { pcs, pair, choose, signedIn, pc } = useSession();
  const { found, available, error } = useDiscovery();
  const paired = new Set(pcs.map((p) => p.serverId));
  const [address, setAddress] = useState('');
  const [testError, setTestError] = useState<string | null>(null);
  const [testBusy, setTestBusy] = useState(false);

  async function connectByAddress() {
    const text = address.trim();
    const link = parsePlainLink(/^https?:\/\//.test(text) ? text : `http://${text.includes(':') ? text : `${text}:8443`}`);
    if (!link) {
      setTestError("Type the address shown on WiFiDrop's Dashboard, for example 192.168.1.20:8443.");
      return;
    }
    if (link.secure) {
      setTestError(HTTPS_OFF_HINT);
      return;
    }
    setTestBusy(true);
    setTestError(null);
    try {
      await pair(await testModePc(link.host, link.port));
      router.replace('/sign-in');
    } catch (e) {
      setTestError(e instanceof ApiError ? `${e.message} ${e.code === 'NETWORK' || e.code === 'TIMEOUT' ? HTTPS_OFF_HINT : ''}` : 'Something went wrong.');
    } finally {
      setTestBusy(false);
    }
  }

  async function openSaved(serverId: string) {
    await choose(serverId);
    router.replace('/');
  }

  async function tryDemo() {
    await pair(DEMO_PC);
    router.replace('/sign-in');
  }

  return (
    <Screen>
      <Title>Connect to your PC</Title>
      <Body muted>
        On your PC, open WiFiDrop and make sure the web server is running. Then scan the QR code on its Dashboard.
      </Body>
      {available ? (
        <Button title="Scan QR code" icon="qr-code" onPress={() => router.push('/scan')} />
      ) : Platform.OS === 'web' ? (
        <Notice kind="warn" text="This preview can't reach a PC. Install WiFiDrop from the App Store or Google Play, or try the demo." />
      ) : (
        <View style={{ gap: 12 }}>
          <Notice kind="warn" text={`Expo Go test mode. ${HTTPS_OFF_HINT} Plain HTTP isn't encrypted, so only test on your own Wi-Fi.`} />
          <Button title="Scan QR code" icon="qr-code" onPress={() => router.push('/scan')} />
          <Field label="Or type the PC's address" value={address} onChangeText={setAddress} placeholder="192.168.1.20:8443"
            keyboardType="url" returnKeyType="go" onSubmitEditing={connectByAddress} />
          <Notice text={testError} />
          <Button title="Connect" kind="secondary" onPress={connectByAddress} busy={testBusy} />
        </View>
      )}

      {available && (
        <View style={{ gap: 8 }}>
          <Text style={{ color: c.muted, fontWeight: '600' }}>FOUND ON THIS WI-FI</Text>
          <Card>
            {found.length === 0 ? (
              <View style={{ flexDirection: 'row', gap: 12, padding: 16, alignItems: 'center' }}>
                <ActivityIndicator color={c.accent} />
                <Body muted>Looking for WiFiDrop PCs…</Body>
              </View>
            ) : (
              found.map((f, i) => (
                <View key={f.serverId}>
                  {i > 0 && <Separator />}
                  <Row
                    icon="desktop-outline"
                    title={f.name}
                    subtitle={paired.has(f.serverId) ? 'Paired' : 'Tap to pair'}
                    onPress={() =>
                      paired.has(f.serverId)
                        ? openSaved(f.serverId)
                        : router.push({ pathname: '/confirm', params: { name: f.name, host: f.host, port: String(f.port), serverId: f.serverId } })
                    }
                  />
                </View>
              ))
            )}
          </Card>
          <Notice kind="warn" text={error} />
        </View>
      )}

      {pcs.filter((p) => !p.demo).length > 0 && (
        <View style={{ gap: 8 }}>
          <Text style={{ color: c.muted, fontWeight: '600' }}>YOUR PCS</Text>
          <Card>
            {pcs.filter((p) => !p.demo).map((p, i) => (
              <View key={p.serverId}>
                {i > 0 && <Separator />}
                <Row
                  icon="desktop"
                  title={p.name}
                  subtitle={p.serverId === pc?.serverId && signedIn ? `Signed in as ${p.username}` : p.username ? `Last signed in as ${p.username}` : undefined}
                  onPress={() => openSaved(p.serverId)}
                />
              </View>
            ))}
          </Card>
        </View>
      )}

      <View style={{ flex: 1 }} />
      <Button title="Try the demo" kind="secondary" icon="play-circle-outline" onPress={tryDemo} />
      <Body muted center>
        WiFiDrop works only on your own Wi-Fi. Your files go straight from your phone to your PC, never through the internet.
      </Body>
    </Screen>
  );
}
