import { router } from 'expo-router';
import { ActivityIndicator, Text, View } from 'react-native';

import { useDiscovery } from '@/state/discovery';
import { DEMO_PC, useSession } from '@/state/session';
import { Body, Button, Card, Notice, Row, Screen, Separator, Title } from '@/ui/kit';
import { useColors } from '@/ui/theme';

export default function Connect() {
  const c = useColors();
  const { pcs, pair, choose, signedIn, pc } = useSession();
  const { found, available, error } = useDiscovery();
  const paired = new Set(pcs.map((p) => p.serverId));

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
      ) : (
        <Notice kind="warn" text="This preview can't reach a PC. Install WiFiDrop from the App Store or Google Play, or try the demo." />
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
