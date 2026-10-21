import { Ionicons } from '@expo/vector-icons';
import { File, Paths } from 'expo-file-system';
import { Redirect, router, Stack, useLocalSearchParams } from 'expo-router';
import * as Sharing from 'expo-sharing';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Alert, FlatList, Platform, Pressable, RefreshControl, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { Item, Listing } from '@/api/types';
import { fileKind, formatBytes, formatWhen, KIND_ICONS } from '@/lib/format';
import { useErrorHandler, useLiveUpdates } from '@/state/hooks';
import { useSession } from '@/state/session';
import { Body, type IconName, Loading, Notice, Row, Separator } from '@/ui/kit';
import { useColors } from '@/ui/theme';
import { pickFiles, pickPhotos, sendToPc } from '@/uploads';
import { UploadSheet, UploadStrip } from '@/uploads/ui';

/** One folder: its subfolders and files. Tapping a file brings it to the phone and opens the share sheet. */
export default function Folder() {
  const c = useColors();
  const { client, signedIn, pc } = useSession();
  const handle = useErrorHandler();
  const { space, folder = 'root', title } = useLocalSearchParams<{ space: string; folder?: string; title?: string }>();
  const [listing, setListing] = useState<Listing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [sheet, setSheet] = useState(false);

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

  function open(item: Item) {
    if (item.kind === 'folder') {
      router.push({ pathname: '/files/[space]', params: { space, folder: item.id, title: item.name } });
    } else {
      share(item);
    }
  }

  async function share(item: Item) {
    if (!client || busyId) return;
    setBusyId(item.id);
    setError(null);
    try {
      const destination = new File(Paths.cache, 'downloads', item.id, item.name).uri;
      const { uri } = await client.download(item, destination);
      if (Platform.OS !== 'web' && (await Sharing.isAvailableAsync())) {
        await Sharing.shareAsync(uri, { dialogTitle: item.name });
      }
    } catch (e) {
      setError(await handle(e));
    } finally {
      setBusyId(null);
    }
  }

  // "My files › Photos": where the files will land, shown in the sheet and the uploads list.
  const label = listing
    ? [listing.space.kind === 'private' ? 'My files' : listing.space.name, ...listing.crumbs.slice(1).map((x) => x.name)].join(' › ')
    : '';

  async function pick(what: 'photos' | 'files') {
    setSheet(false);
    if (!listing || !pc) return;
    try {
      const picked = what === 'photos' ? await pickPhotos() : await pickFiles();
      if (picked === 'denied') {
        Alert.alert('Photos access is off', 'To send photos and videos, allow WiFiDrop to access your photos in Settings.');
        return;
      }
      if (picked.length) {
        await sendToPc(picked, { serverId: pc.serverId, spaceId: listing.space.id, parentId: listing.folder_id, label });
      }
    } catch {
      setError("Couldn't open your photos or files. Try again.");
    }
  }

  if (!client || !signedIn) return <Redirect href="/" />;
  const heading = folder === 'root' ? title ?? listing?.space.name : listing?.crumbs.at(-1)?.name ?? title;

  return (
    <SafeAreaView edges={['bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: c.bg }}>
      <Stack.Screen
        options={{
          title: heading ?? '',
          headerRight: () =>
            listing?.can_upload ? (
              <Pressable accessibilityRole="button" accessibilityLabel="Upload to this folder" hitSlop={12} onPress={() => setSheet(true)}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                <Ionicons name="cloud-upload-outline" size={24} color={c.accent} />
                <Text style={{ color: c.accent, fontSize: 16, fontWeight: '600' }}>Upload</Text>
              </Pressable>
            ) : null,
        }}
      />
      <UploadSheet visible={sheet} folder={label} onClose={() => setSheet(false)} onPick={pick} />
      {listing === null && !error ? (
        <Loading />
      ) : (
        <FlatList
          data={listing?.items ?? []}
          keyExtractor={(i) => i.id}
          contentContainerStyle={{ paddingBottom: 24, maxWidth: 720, width: '100%', alignSelf: 'center' }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.accent} />}
          ItemSeparatorComponent={Separator}
          ListHeaderComponent={
            <View style={{ padding: error || listing?.space.level === 'view' ? 16 : 0, gap: 12 }}>
              <Notice text={error} />
              {listing?.space.level === 'view' && <Notice kind="warn" text="You can view and download here, but not add or change things." />}
            </View>
          }
          ListEmptyComponent={
            listing ? (
              <View style={{ alignItems: 'center', padding: 40, gap: 12 }}>
                <Ionicons name="folder-open-outline" size={48} color={c.muted} />
                <Body muted center>{listing.can_upload ? 'This folder is empty. Tap Upload to add photos or files.' : 'This folder is empty.'}</Body>
              </View>
            ) : undefined
          }
          renderItem={({ item }) => {
            const kind = fileKind(item.name, item.kind === 'folder');
            const subtitle = item.kind === 'folder'
              ? `${item.child_count ?? 0} item${item.child_count === 1 ? '' : 's'}`
              : `${formatBytes(item.size)} · ${formatWhen(item.modified_at)}${item.mine ? '' : ` · ${item.created_by_name}`}`;
            return (
              <Row
                icon={KIND_ICONS[kind] as IconName}
                iconColor={c[kind === 'file' ? 'doc' : kind]}
                title={item.name}
                subtitle={subtitle}
                onPress={() => open(item)}
                accessibilityHint={item.kind === 'folder' ? 'Opens the folder' : 'Downloads the file and opens the share sheet'}
                right={busyId === item.id ? <ActivityIndicator color={c.accent} /> : item.kind === 'file'
                  ? <Ionicons name="share-outline" size={20} color={c.muted} /> : undefined}
              />
            );
          }}
        />
      )}
      {listing && listing.items.length > 0 && (
        <Text style={{ color: c.muted, textAlign: 'center', paddingBottom: 8, fontSize: 13 }}>Tap a file to save or share it</Text>
      )}
      <UploadStrip />
    </SafeAreaView>
  );
}
