import { Ionicons } from '@expo/vector-icons';
import { router, Stack } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { Item, SearchResult, Space } from '@/api/types';
import { formatBytes } from '@/lib/format';
import { useErrorHandler, useLiveUpdates } from '@/state/hooks';
import { fetchToPhone, openItem, shareFile } from '@/state/open';
import { useSession } from '@/state/session';
import { Body, Button, Card, Loading, Logo, Notice, Row, SearchField, SectionTitle, Separator } from '@/ui/kit';
import { radius, useColors } from '@/ui/theme';
import { Thumb } from '@/ui/thumb';
import { useSendTo } from '@/uploads/pick';
import { UploadStrip } from '@/uploads/ui';

/** Home: which PC you're on, search, quick send, your files and the shared folders you're in. */
export default function Home() {
  const c = useColors();
  const { client, pc, me, setMe, signedIn } = useSession();
  const handle = useErrorHandler();
  const sendTo = useSendTo();
  const [spaces, setSpaces] = useState<Space[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

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

  // Search as you type, a moment after the last key.
  const q = query.trim();
  useEffect(() => {
    if (!q || !client) return;
    let live = true;
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const found = await client.search(q);
        if (live) setResults(found);
      } catch (e) {
        if (live) setError(await handle(e));
      } finally {
        if (live) setSearching(false);
      }
    }, 250);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [q, client, handle]);

  const refresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  async function share(item: Item) {
    if (!client || busyId) return;
    setBusyId(item.id);
    try {
      await shareFile(await fetchToPhone(client, item), item.name);
    } catch (e) {
      setError(await handle(e));
    } finally {
      setBusyId(null);
    }
  }

  const mine = spaces?.find((s) => s.kind === 'private');
  const shared = spaces?.filter((s) => s.kind === 'shared') ?? [];
  const name = me?.user.display_name || me?.user.username;
  const offline = !!error && spaces === null;
  const showResults = !!q && (results !== null || searching);

  async function quickSend(what: 'photos' | 'files') {
    if (!mine) return;
    try {
      await sendTo(what, { spaceId: mine.id, parentId: mine.root_id, label: 'My files' });
    } catch (e) {
      setError(`Couldn't open your ${what}. ${(e as Error)?.message ?? ''}`.trim());
    }
  }

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: c.bg }}>
      <Stack.Screen options={{ headerShown: false }} />
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.accent} />}>
        <View style={styles.header}>
          <Logo size={34} />
          <Text style={[styles.brand, { color: c.text }]}>WiFiDrop</Text>
          <Pressable accessibilityRole="button" accessibilityLabel="Uploads" hitSlop={10} onPress={() => router.push('/uploads')}>
            <Ionicons name="cloud-upload-outline" size={26} color={c.text} />
          </Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel="Settings" hitSlop={10} onPress={() => router.push('/settings')}>
            <Ionicons name="settings-outline" size={25} color={c.text} />
          </Pressable>
        </View>

        <Pressable accessibilityRole="button" accessibilityHint="Opens settings for this PC" onPress={() => router.push('/settings')}
          style={[styles.pcCard, { backgroundColor: c.surface, borderColor: c.border }]}>
          <View style={[styles.square, { backgroundColor: c.surface2 }]}>
            <Ionicons name="desktop" size={22} color={c.accent} />
          </View>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text numberOfLines={1} style={{ color: c.text, fontSize: 16, fontWeight: '700' }}>{pc?.name ?? 'Your PC'}</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 }}>
              <View style={[styles.dot, { backgroundColor: offline ? c.danger : c.ok }]} />
              <Text numberOfLines={1} style={{ color: c.muted, fontSize: 13, flexShrink: 1 }}>
                {offline ? "Can't reach it right now" : name ? `Connected · ${name}` : 'Connected'}
                {pc?.insecure ? ' · test mode' : ''}
              </Text>
            </View>
          </View>
          {me?.edition === 'pro' && (
            <View style={[styles.pro, { borderColor: c.warn }]}><Text style={{ color: c.warn, fontSize: 11, fontWeight: '800' }}>PRO</Text></View>
          )}
        </Pressable>

        <SearchField value={query} onChangeText={(t) => { setQuery(t); if (!t.trim()) setResults(null); }} placeholder="Search all your files" />

        <Notice text={error} />
        {offline && <Button title="Try again" icon="refresh" onPress={load} />}
        {me?.status.downloads_paused && <Notice kind="warn" text="Downloads are paused on the PC for now." />}
        {me?.status.uploads_paused && <Notice kind="warn" text="Uploads are paused on the PC for now." />}

        {showResults ? (
          <View style={{ gap: 8 }}>
            <SectionTitle right={searching ? <ActivityIndicator color={c.accent} /> : undefined}>
              {results ? `${results.length} RESULT${results.length === 1 ? '' : 'S'}` : 'SEARCHING'}
            </SectionTitle>
            {results && results.length === 0 && !searching && <Body muted>Nothing called "{q}".</Body>}
            {results && results.length > 0 && (
              <Card>
                {results.map((r, i) => {
                  const where = [r.space.kind === 'private' ? 'My files' : r.space.name, ...r.path].join(' › ');
                  return (
                    <View key={r.id}>
                      {i > 0 && <Separator />}
                      <Row
                        lead={<Thumb item={r} />}
                        title={r.name}
                        subtitle={r.kind === 'folder' ? where : `${where} · ${formatBytes(r.size)}`}
                        onPress={() => openItem(r, r.space.id, share)}
                        right={busyId === r.id ? <ActivityIndicator color={c.accent} /> : undefined}
                      />
                    </View>
                  );
                })}
              </Card>
            )}
          </View>
        ) : spaces === null && !error ? (
          <View style={{ paddingTop: 40 }}><Loading /></View>
        ) : (
          <>
            {mine && !me?.status.uploads_paused && (
              <View style={styles.tiles}>
                <QuickTile icon="images" color={c.image} title="Send photos" subtitle="Full-quality originals" onPress={() => quickSend('photos')} />
                <QuickTile icon="document-attach" color={c.doc} title="Send files" subtitle="From the Files app" onPress={() => quickSend('files')} />
              </View>
            )}

            {mine && (
              <Card>
                <Row lead={<Badge icon="person" color={c.accent} />} title="My files"
                  subtitle={`${formatBytes(mine.used_bytes)}${mine.quota_bytes ? ` of ${formatBytes(mine.quota_bytes)}` : ''} · only you`}
                  onPress={() => router.push({ pathname: '/files/[space]', params: { space: mine.id, title: 'My files' } })} />
              </Card>
            )}

            {shared.length > 0 && (
              <View style={{ gap: 8 }}>
                <SectionTitle>SHARED FOLDERS</SectionTitle>
                <Card>
                  {shared.map((s, i) => (
                    <View key={s.id}>
                      {i > 0 && <Separator />}
                      <Row lead={<Badge icon="people" color={c.folder} />} title={s.name}
                        subtitle={s.level === 'view' ? `${formatBytes(s.used_bytes)} · view only` : `${formatBytes(s.used_bytes)} · you can add files`}
                        onPress={() => router.push({ pathname: '/files/[space]', params: { space: s.id, title: s.name } })} />
                    </View>
                  ))}
                </Card>
              </View>
            )}
          </>
        )}
      </ScrollView>
      <UploadStrip />
    </SafeAreaView>
  );
}

function QuickTile({ icon, color, title, subtitle, onPress }: {
  icon: 'images' | 'document-attach'; color: string; title: string; subtitle: string; onPress: () => void;
}) {
  const c = useColors();
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={title} onPress={onPress}
      style={({ pressed }) => [styles.tile, { backgroundColor: c.surface, borderColor: c.border, opacity: pressed ? 0.85 : 1 }]}>
      <View style={[styles.square, { backgroundColor: c.surface2, width: 40, height: 40, marginBottom: 6 }]}>
        <Ionicons name={icon} size={22} color={color} />
      </View>
      <Text style={{ color: c.text, fontWeight: '700', fontSize: 15 }}>{title}</Text>
      <Text style={{ color: c.muted, fontSize: 12 }}>{subtitle}</Text>
    </Pressable>
  );
}

function Badge({ icon, color }: { icon: 'person' | 'people'; color: string }) {
  const c = useColors();
  return (
    <View style={[styles.square, { backgroundColor: c.surface2 }]}>
      <Ionicons name={icon} size={22} color={color} />
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, paddingTop: 8, gap: 16, maxWidth: 600, width: '100%', alignSelf: 'center', paddingBottom: 40 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  brand: { flex: 1, fontSize: 26, fontWeight: '800', letterSpacing: -0.5 },
  pcCard: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: radius + 2, borderWidth: StyleSheet.hairlineWidth },
  square: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 8, height: 8, borderRadius: 4 },
  pro: { borderWidth: 1, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  tiles: { flexDirection: 'row', gap: 12 },
  tile: { flex: 1, padding: 14, gap: 2, borderRadius: radius + 2, borderWidth: StyleSheet.hairlineWidth },
});
