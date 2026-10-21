// Upload pieces shared by screens: the "what do you want to send" sheet and the progress strip.
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useRef } from 'react';
import { Modal, Platform, Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button, ProgressBar, Row, Separator } from '@/ui/kit';
import { radius, useColors } from '@/ui/theme';

import { summarize, useUploads } from '.';

/**
 * iOS can't show the photo or file picker while this sheet is still sliding away, so the choice is
 * remembered and the picker opens once the sheet has gone.
 */
export function UploadSheet({ visible, folder, onClose, onPick }: {
  visible: boolean; folder: string; onClose: () => void; onPick: (what: 'photos' | 'files') => void;
}) {
  const c = useColors();
  const insets = useSafeAreaInsets();
  const pending = useRef<'photos' | 'files' | null>(null);

  const launch = () => {
    const what = pending.current;
    pending.current = null;
    if (what) onPick(what);
  };

  const choose = (what: 'photos' | 'files') => {
    pending.current = what;
    onClose();
    // onDismiss only exists on iOS; elsewhere wait for the slide-out animation.
    setTimeout(launch, Platform.OS === 'ios' ? 900 : 350);
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} onDismiss={launch}>
      <Pressable accessibilityLabel="Close" style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.5)' }} onPress={onClose} />
      <View style={{ backgroundColor: c.surface, borderTopLeftRadius: radius * 1.5, borderTopRightRadius: radius * 1.5,
                     padding: 16, paddingBottom: 16 + insets.bottom, gap: 12 }}>
        <Text style={{ color: c.muted, textAlign: 'center' }} numberOfLines={1}>Send to {folder}</Text>
        <View style={{ borderRadius: radius, overflow: 'hidden', backgroundColor: c.surface2 }}>
          <Row icon="images" iconColor={c.image} title="Photos & videos" subtitle="Originals, full quality"
            onPress={() => choose('photos')} />
          <Separator />
          <Row icon="document" iconColor={c.doc} title="Files" subtitle="From the Files app" onPress={() => choose('files')} />
        </View>
        <Button title="Cancel" kind="secondary" onPress={onClose} />
      </View>
    </Modal>
  );
}

/** A strip under a screen while files are being sent; tap it for the details. */
export function UploadStrip() {
  const c = useColors();
  const s = summarize(useUploads());
  if (!s.active && !s.failed) return null;
  const text = s.active
    ? `Sending ${s.active} file${s.active === 1 ? '' : 's'} · ${Math.round(s.progress * 100)}%`
    : `${s.failed} upload${s.failed === 1 ? '' : 's'} couldn't be sent`;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityHint="Shows your uploads"
      onPress={() => router.push('/uploads')}
      style={{ padding: 12, paddingHorizontal: 16, gap: 8, borderTopWidth: 1, borderColor: c.border, backgroundColor: c.surface }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name={s.active ? 'cloud-upload' : 'alert-circle'} size={18} color={s.active ? c.accent : c.danger} />
        <Text style={{ color: c.text, flex: 1, fontWeight: '500' }}>{text}</Text>
        <Ionicons name="chevron-forward" size={16} color={c.muted} />
      </View>
      {s.active > 0 && <ProgressBar value={s.progress} />}
    </Pressable>
  );
}
