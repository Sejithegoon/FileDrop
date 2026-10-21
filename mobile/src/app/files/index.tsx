import { Ionicons } from '@expo/vector-icons';
import { router, Stack } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { Space } from '@/api/types';
import { formatBytes } from '@/lib/format';
import { useErrorHandler, useLiveUpdates } from '@/state/hooks';
import { useSession } from '@/state/session';
import { Button, Card, Loading, Notice, Row, Separator } from '@/ui/kit';
import { useColors } from '@/ui/theme';

/** The places this person can open: their own files and the shared folders they're in. */
export default function Home() {
  const c = useColors();
  const { client, pc, me, setMe, signedIn } = useSession();
  const handle = useErrorHandler();
  const [spaces, setSpaces] = useState<Space[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    if (!client) return;
    try {
      const [who, list] = await Promise.all([client.me(), client.spaces()]);
      setMe(who);
      setSpaces(list);
      setError(null);
    } catch (e) {
      setError(await handle(e));
    }
  }, [client, setMe, handle]);

  useEffect(() => {
    if (!signedIn) router.replace('/');
  }, [signedIn]);

  useLiveUpdates(client, load);

  const refresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const mine = spaces?.filter((s) => s.kind === 'private') ?? [];
  const shared = spaces?.filter((s) => s.kind === 'shared') ?? [];

  return (
    <SafeAreaView edges={['bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: c.bg }}>
      <Stack.Screen
        options={{
          title: pc?.name ?? 'WiFiDrop',
          headerRight: () => (
            <Pressable accessibilityRole="button" accessibilityLabel="Settings" hitSlop={12} onPress={() => router.push('/settings')}>
              <Ionicons name="settings-outline" size={24} color={c.accent} />
            </Pressable>
          ),
        }}
      />
      {spaces === null && !error ? (
        <Loading />
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: 20, gap: 16, maxWidth: 560, width: '100%', alignSelf: 'center' }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.accent} />}>
          {me && <Text style={{ color: c.muted }}>Signed in as {me.user.display_name || me.user.username}</Text>}
          <Notice text={error} />
          {error && spaces === null && <Button title="Try again" icon="refresh" onPress={load} />}
          {me?.status.downloads_paused && <Notice kind="warn" text="Downloads are paused on the PC for now." />}
          {mine.length > 0 && (
            <Card>
              {mine.map((s) => (
                <Row key={s.id} icon="person-circle" title="My files" subtitle={formatBytes(s.used_bytes)}
                  onPress={() => router.push({ pathname: '/files/[space]', params: { space: s.id, title: 'My files' } })} />
              ))}
            </Card>
          )}
          {shared.length > 0 && (
            <View style={{ gap: 8 }}>
              <Text style={{ color: c.muted, fontWeight: '600' }}>SHARED FOLDERS</Text>
              <Card>
                {shared.map((s, i) => (
                  <View key={s.id}>
                    {i > 0 && <Separator />}
                    <Row icon="people" iconColor={c.folder} title={s.name}
                      subtitle={s.level === 'view' ? 'View only' : formatBytes(s.used_bytes)}
                      onPress={() => router.push({ pathname: '/files/[space]', params: { space: s.id, title: s.name } })} />
                  </View>
                ))}
              </Card>
            </View>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
