import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { Stack, useLocalSearchParams } from 'expo-router';
import { useVideoPlayer, VideoView } from 'expo-video';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { fileKind, formatBytes } from '@/lib/format';
import { useErrorHandler } from '@/state/hooks';
import { fetchToPhone, shareFile } from '@/state/open';
import { useSession } from '@/state/session';
import { Button } from '@/ui/kit';

/** A photo or video, full screen, with Share. The file comes to the phone first (kept in its cache). */
export default function Viewer() {
  const { client } = useSession();
  const handle = useErrorHandler();
  const { id, name, size } = useLocalSearchParams<{ id: string; name: string; size: string }>();
  const [uri, setUri] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const isVideo = fileKind(name) === 'video';

  useEffect(() => {
    let live = true;
    if (client) {
      fetchToPhone(client, { id, name, size: Number(size) })
        .then((u) => live && setUri(u))
        .catch(async (e) => live && setError(await handle(e)));
    }
    return () => {
      live = false;
    };
  }, [client, id, name, size, handle, attempt]);

  return (
    <SafeAreaView edges={['bottom']} style={styles.screen}>
      <Stack.Screen
        options={{
          title: name,
          headerStyle: { backgroundColor: '#000' },
          headerTintColor: '#fff',
          headerTitleStyle: { color: '#fff' },
          headerRight: () =>
            uri ? (
              <Pressable accessibilityRole="button" accessibilityLabel="Share" hitSlop={12} onPress={() => shareFile(uri, name)}>
                <Ionicons name="share-outline" size={24} color="#fff" />
              </Pressable>
            ) : null,
        }}
      />
      {error ? (
        <View style={styles.center}>
          <Ionicons name="alert-circle-outline" size={44} color="#f87171" />
          <Text style={styles.message}>{error}</Text>
          <Button title="Try again" icon="refresh" onPress={() => { setError(null); setAttempt((n) => n + 1); }} />
        </View>
      ) : !uri ? (
        <View style={styles.center}>
          <ActivityIndicator color="#fff" size="large" />
          <Text style={styles.message}>Getting {name} from your PC{size ? ` (${formatBytes(Number(size))})` : ''}…</Text>
        </View>
      ) : isVideo ? (
        <Player uri={uri} />
      ) : (
        <Image source={{ uri }} style={StyleSheet.absoluteFill} contentFit="contain" accessibilityLabel={name} />
      )}
    </SafeAreaView>
  );
}

function Player({ uri }: { uri: string }) {
  const player = useVideoPlayer(uri, (p) => {
    p.play();
  });
  return <VideoView player={player} style={StyleSheet.absoluteFill} nativeControls contentFit="contain" fullscreenOptions={{ enable: true }} />;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#000' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16, padding: 32 },
  message: { color: '#cbd5e1', fontSize: 16, textAlign: 'center' },
});
