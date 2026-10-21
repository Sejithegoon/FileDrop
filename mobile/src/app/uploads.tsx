import { Ionicons } from '@expo/vector-icons';
import { Stack } from 'expo-router';
import { FlatList, Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { fileKind, formatBytes, KIND_ICONS } from '@/lib/format';
import { useSession } from '@/state/session';
import { Body, type IconName, Notice, ProgressBar, Separator } from '@/ui/kit';
import { useColors } from '@/ui/theme';
import { type Job, queue, summarize, useUploads } from '@/uploads';

const ORDER: Record<Job['status'], number> = { sending: 0, waiting: 1, failed: 2, done: 3, cancelled: 4 };

/** Everything being sent to the PC, with progress, and cancel / try again. */
export default function Uploads() {
  const c = useColors();
  const { pc } = useSession();
  const jobs = useUploads();
  const sorted = [...jobs].sort((a, b) => ORDER[a.status] - ORDER[b.status] || a.addedAt - b.addedAt);
  const s = summarize(jobs);
  const otherPc = jobs.some((j) => (j.status === 'waiting' || j.status === 'failed') && j.serverId !== pc?.serverId);

  return (
    <SafeAreaView edges={['bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: c.bg }}>
      <Stack.Screen
        options={{
          headerRight: () =>
            s.done || jobs.some((j) => j.status === 'cancelled') ? (
              <Pressable accessibilityRole="button" hitSlop={12} onPress={() => queue.clearFinished()}>
                <Text style={{ color: c.accent, fontSize: 16 }}>Clear done</Text>
              </Pressable>
            ) : null,
        }}
      />
      <FlatList
        data={sorted}
        keyExtractor={(j) => j.id}
        contentContainerStyle={{ paddingBottom: 24, maxWidth: 720, width: '100%', alignSelf: 'center' }}
        ItemSeparatorComponent={Separator}
        ListHeaderComponent={
          <View style={{ padding: 16, gap: 12 }}>
            {s.active > 0 && (
              <View style={{ gap: 8 }}>
                <Text style={{ color: c.text, fontSize: 16, fontWeight: '600' }}>
                  Sending {s.active} file{s.active === 1 ? '' : 's'} · {Math.round(s.progress * 100)}%
                </Text>
                <ProgressBar value={s.progress} />
                <Body muted>Keep WiFiDrop open until it's done. If you leave, it carries on when you come back.</Body>
              </View>
            )}
            {otherPc && <Notice kind="warn" text="Some uploads are for another PC. They continue when you switch back to it." />}
          </View>
        }
        ListEmptyComponent={
          <View style={{ alignItems: 'center', padding: 40, gap: 12 }}>
            <Ionicons name="cloud-done-outline" size={48} color={c.muted} />
            <Body muted center>Nothing being sent. Open a folder and tap Upload.</Body>
          </View>
        }
        renderItem={({ item }) => <UploadRow job={item} />}
      />
    </SafeAreaView>
  );
}

function UploadRow({ job }: { job: Job }) {
  const c = useColors();
  const kind = fileKind(job.name);
  const fraction = job.size ? job.sent / job.size : job.status === 'done' ? 1 : 0;
  const status = {
    sending: `${formatBytes(job.sent)} of ${formatBytes(job.size)}`,
    waiting: job.error ?? 'Waiting…',
    failed: job.error ?? "Couldn't send",
    done: `Sent · ${formatBytes(job.size)}`,
    cancelled: 'Cancelled',
  }[job.status];
  const statusColor = job.status === 'failed' ? c.danger : job.status === 'done' ? c.ok : job.error ? c.warn : c.muted;
  return (
    <View style={{ flexDirection: 'row', gap: 14, paddingHorizontal: 16, paddingVertical: 12, alignItems: 'center' }}>
      <Ionicons name={KIND_ICONS[kind] as IconName} size={26} color={c[kind === 'file' ? 'doc' : kind]} />
      <View style={{ flex: 1, minWidth: 0, gap: 4 }}>
        <Text numberOfLines={1} style={{ color: c.text, fontSize: 16, fontWeight: '500' }}>{job.name}</Text>
        <Text numberOfLines={1} style={{ color: c.muted, fontSize: 13 }}>To {job.folderLabel}</Text>
        {(job.status === 'sending' || job.status === 'waiting') && <ProgressBar value={fraction} />}
        <Text numberOfLines={2} style={{ color: statusColor, fontSize: 13 }}>{status}</Text>
      </View>
      {job.status === 'failed' && (
        <Pressable accessibilityRole="button" accessibilityLabel={`Try ${job.name} again`} hitSlop={10} onPress={() => queue.retry(job.id)}>
          <Ionicons name="refresh" size={22} color={c.accent} />
        </Pressable>
      )}
      {(job.status === 'sending' || job.status === 'waiting' || job.status === 'failed') && (
        <Pressable accessibilityRole="button" accessibilityLabel={`Cancel ${job.name}`} hitSlop={10} onPress={() => queue.cancel(job.id)}>
          <Ionicons name="close-circle" size={24} color={c.muted} />
        </Pressable>
      )}
      {job.status === 'done' && <Ionicons name="checkmark-circle" size={24} color={c.ok} />}
    </View>
  );
}
