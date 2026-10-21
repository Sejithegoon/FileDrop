import { Ionicons } from '@expo/vector-icons';
import { Redirect, Stack, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, RefreshControl, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { Item, Listing } from '@/api/types';
import { formatBytes, formatWhen } from '@/lib/format';
import { useErrorHandler, useLiveUpdates } from '@/state/hooks';
import { fetchToPhone, openItem, shareFile } from '@/state/open';
import { setPref, usePrefs } from '@/state/prefs';
import { useSession } from '@/state/session';
import { Body, Fab, Loading, Notice, Row, Separator } from '@/ui/kit';
import { radius, useColors } from '@/ui/theme';
import { Thumb } from '@/ui/thumb';
import { useSendTo } from '@/uploads/pick';
import { summarize, useUploads } from '@/uploads';
import { UploadSheet, UploadStrip } from '@/uploads/ui';

/** One folder. Photos and videos open in the viewer; other files go to the share sheet. */
export default function Folder() {
  const c = useColors();
  const { client, signedIn, pc } = useSession();
  const { folderView } = usePrefs();
  const handle = useErrorHandler();
  const sendTo = useSendTo();
  const { width } = useWindowDimensions();
  const { space, folder = 'root', title } = useLocalSearchParams<{ space: string; folder?: string; title?: string }>();
  const [listing, setListing] = useState<Listing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [sheet, setSheet] = useState(false);
  const uploads = summarize(useUploads());

  const load = useCallback(async () => {
    if (!client) return;
    try {
      setListing(await client.listing(space, folder));
      setError(null);
    } catch (e) {
      setError(await handle(e));
    }
  }, [client, space, folder, handle]);

  useLiveUpdates(client, load);

  async function refresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  async function share(item: Item) {
    if (!client || busyId) return;
    setBusyId(item.id);
    setError(null);
    try {
      await shareFile(await fetchToPhone(client, item), item.name);
    } catch (e) {
      setError(await handle(e));
    } finally {
      setBusyId(null);
    }
  }

  // "My files › Photos": where uploads land, shown in the sheet and the uploads list.
  const label = listing
    ? [listing.space.kind === 'private' ? 'My files' : listing.space.name, ...listing.crumbs.slice(1).map((x) => x.name)].join(' › ')
    : '';

  async function pick(what: 'photos' | 'files') {
    if (!listing || !pc) return;
    try {
      await sendTo(what, { spaceId: listing.space.id, parentId: listing.folder_id, label });
    } catch (e) {
      setError(`Couldn't open your ${what === 'photos' ? 'photos' : 'files'}. ${(e as Error)?.message ?? ''}`.trim());
    }
  }

  if (!client || !signedIn) return <Redirect href="/" />;
  const heading = folder === 'root' ? title ?? listing?.space.name : listing?.crumbs.at(-1)?.name ?? title;
  const grid = folderView === 'grid';
  const columns = Math.max(3, Math.floor(Math.min(width, 900) / 130));
  const tile = (Math.min(width, 900) - 16 * 2 - 10 * (columns - 1)) / columns;
  const canUpload = !!listing?.can_upload;

  return (
    <SafeAreaView edges={['bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: c.bg }}>
      <Stack.Screen
        options={{
          title: heading ?? '',
          headerRight: () => (
            <Pressable accessibilityRole="button" accessibilityLabel={grid ? 'Show as list' : 'Show as grid'} hitSlop={12}
              onPress={() => setPref('folderView', grid ? 'list' : 'grid')}>
              <Ionicons name={grid ? 'list' : 'grid-outline'} size={22} color={c.accent} />
            </Pressable>
          ),
        }}
      />
      <UploadSheet visible={sheet} folder={label} onClose={() => setSheet(false)} onPick={pick} />
      {listing === null && !error ? (
        <Loading />
      ) : (
        <FlatList
          key={grid ? `grid-${columns}` : 'list'}
          data={listing?.items ?? []}
          keyExtractor={(i) => i.id}
          numColumns={grid ? columns : 1}
          columnWrapperStyle={grid ? { gap: 10, paddingHorizontal: 16 } : undefined}
          contentContainerStyle={{ paddingBottom: canUpload ? 110 : 24, gap: grid ? 14 : 0, maxWidth: 900, width: '100%', alignSelf: 'center' }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.accent} />}
          ItemSeparatorComponent={grid ? undefined : Separator}
          ListHeaderComponent={
            error || listing?.space.level === 'view' ? (
              <View style={{ padding: 16, gap: 12 }}>
                <Notice text={error} />
                {listing?.space.level === 'view' && <Notice kind="warn" text="You can view and download here, but not add or change things." />}
              </View>
            ) : <View style={{ height: grid ? 6 : 0 }} />
          }
          ListEmptyComponent={
            listing ? (
              <View style={styles.empty}>
                <View style={[styles.emptyIcon, { backgroundColor: c.surface }]}>
                  <Ionicons name="folder-open-outline" size={40} color={c.folder} />
                </View>
                <Text style={{ color: c.text, fontSize: 18, fontWeight: '700' }}>Nothing here yet</Text>
                <Body muted center>{canUpload ? 'Tap Upload to send photos, videos or files to this folder.' : 'Files added on the PC show up here.'}</Body>
              </View>
            ) : null
          }
          renderItem={({ item }) => grid
            ? <GridTile item={item} size={tile} busy={busyId === item.id} onPress={() => openItem(item, space, share)} onLongPress={() => item.kind === 'file' && share(item)} />
            : (
              <Row
                lead={<Thumb item={item} size={48} />}
                title={item.name}
                subtitle={item.kind === 'folder'
                  ? `${item.child_count ?? 0} item${item.child_count === 1 ? '' : 's'}`
                  : `${formatBytes(item.size)} · ${formatWhen(item.modified_at)}${item.mine ? '' : ` · ${item.created_by_name}`}`}
                onPress={() => openItem(item, space, share)}
                onLongPress={() => item.kind === 'file' && share(item)}
                accessibilityHint={item.kind === 'folder' ? 'Opens the folder' : 'Opens the file. Long press to share it.'}
                right={busyId === item.id ? <ActivityIndicator color={c.accent} /> : item.kind === 'file' ? (
                  <Pressable accessibilityRole="button" accessibilityLabel={`Share ${item.name}`} hitSlop={10} onPress={() => share(item)}>
                    <Ionicons name="share-outline" size={20} color={c.muted} />
                  </Pressable>
                ) : undefined}
              />
            )}
        />
      )}
      {canUpload && <Fab icon="cloud-upload" label="Upload" onPress={() => setSheet(true)} bottom={uploads.active || uploads.failed ? 96 : 24} />}
      <UploadStrip />
    </SafeAreaView>
  );
}

function GridTile({ item, size, busy, onPress, onLongPress }: {
  item: Item; size: number; busy: boolean; onPress: () => void; onLongPress: () => void;
}) {
  const c = useColors();
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={item.name} onPress={onPress} onLongPress={onLongPress}
      style={({ pressed }) => ({ width: size, opacity: pressed ? 0.8 : 1, gap: 6 })}>
      <View>
        <Thumb item={item} size={size} radius={radius} style={{ backgroundColor: c.surface }} />
        {busy && <View style={[StyleSheet.absoluteFill, styles.busy]}><ActivityIndicator color="#fff" /></View>}
      </View>
      <Text numberOfLines={1} style={{ color: c.text, fontSize: 13, fontWeight: '500' }}>{item.name}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  empty: { alignItems: 'center', padding: 40, gap: 10 },
  emptyIcon: { width: 80, height: 80, borderRadius: 24, alignItems: 'center', justifyContent: 'center', marginBottom: 6 },
  busy: { alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(0,0,0,0.45)', borderRadius: radius },
});
