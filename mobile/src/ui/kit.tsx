// Small building blocks shared by the screens.
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import type { ComponentProps, ReactNode } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, type TextInputProps, View, type ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { radius, useColors } from './theme';

export type IconName = ComponentProps<typeof Ionicons>['name'];

export function Screen({ children, scroll = true }: { children: ReactNode; scroll?: boolean }) {
  const c = useColors();
  const body = <View style={styles.inner}>{children}</View>;
  return (
    <SafeAreaView edges={['bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: c.bg }}>
      {scroll ? <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">{body}</ScrollView> : body}
    </SafeAreaView>
  );
}

export function Title({ children }: { children: ReactNode }) {
  const c = useColors();
  return <Text accessibilityRole="header" style={[styles.title, { color: c.text }]}>{children}</Text>;
}

export function Body({ children, muted, center }: { children: ReactNode; muted?: boolean; center?: boolean }) {
  const c = useColors();
  return <Text style={[styles.body, { color: muted ? c.muted : c.text, textAlign: center ? 'center' : 'left' }]}>{children}</Text>;
}

export function Button({ title, onPress, kind = 'primary', icon, busy, disabled }: {
  title: string; onPress: () => void; kind?: 'primary' | 'secondary' | 'danger'; icon?: IconName; busy?: boolean; disabled?: boolean;
}) {
  const c = useColors();
  const bg = kind === 'primary' ? c.accent : c.surface2;
  const fg = kind === 'primary' ? c.accentInk : kind === 'danger' ? c.danger : c.text;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: disabled || busy, busy }}
      disabled={disabled || busy}
      onPress={onPress}
      style={({ pressed }) => [styles.button, { backgroundColor: bg, borderColor: c.border, opacity: disabled ? 0.5 : pressed ? 0.8 : 1 }]}>
      {busy ? <ActivityIndicator color={fg} /> : icon ? <Ionicons name={icon} size={20} color={fg} /> : null}
      <Text style={[styles.buttonText, { color: fg }]}>{title}</Text>
    </Pressable>
  );
}

export function Field({ label, ...props }: TextInputProps & { label: string }) {
  const c = useColors();
  return (
    <View style={{ gap: 6 }}>
      <Text style={[styles.label, { color: c.muted }]}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={c.muted}
        autoCapitalize="none"
        autoCorrect={false}
        {...props}
        style={[styles.input, { color: c.text, backgroundColor: c.surface, borderColor: c.border }]}
      />
    </View>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  const c = useColors();
  return <View style={[styles.card, { backgroundColor: c.surface, borderColor: c.border }, style]}>{children}</View>;
}

export function Row({ icon, iconColor, lead, title, subtitle, onPress, onLongPress, right, accessibilityHint }: {
  icon?: IconName; iconColor?: string; lead?: ReactNode; title: string; subtitle?: string; onPress?: () => void;
  onLongPress?: () => void; right?: ReactNode; accessibilityHint?: string;
}) {
  const c = useColors();
  return (
    <Pressable
      accessibilityRole={onPress ? 'button' : undefined}
      accessibilityHint={accessibilityHint}
      onPress={onPress}
      onLongPress={onLongPress}
      disabled={!onPress && !onLongPress}
      style={({ pressed }) => [styles.row, { backgroundColor: pressed ? c.surface2 : 'transparent' }]}>
      {lead ?? (icon ? <Ionicons name={icon} size={26} color={iconColor ?? c.accent} /> : null)}
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text numberOfLines={1} style={[styles.rowTitle, { color: c.text }]}>{title}</Text>
        {subtitle ? <Text numberOfLines={1} style={[styles.rowSub, { color: c.muted }]}>{subtitle}</Text> : null}
      </View>
      {right ?? (onPress ? <Ionicons name="chevron-forward" size={18} color={c.muted} /> : null)}
    </Pressable>
  );
}

export function Separator() {
  const c = useColors();
  return <View style={{ height: StyleSheet.hairlineWidth, backgroundColor: c.border, marginLeft: 74 }} />;
}

export function Notice({ text, kind = 'danger' }: { text: string | null; kind?: 'danger' | 'warn' | 'ok' }) {
  const c = useColors();
  if (!text) return null;
  const color = c[kind];
  return (
    <View accessibilityLiveRegion="polite" style={[styles.notice, { borderColor: color }]}>
      <Ionicons name={kind === 'ok' ? 'checkmark-circle' : 'alert-circle'} size={20} color={color} />
      <Text style={[styles.body, { color: c.text, flex: 1 }]}>{text}</Text>
    </View>
  );
}

export function Loading() {
  const c = useColors();
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: c.bg }}>
      <ActivityIndicator color={c.accent} size="large" />
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1 },
  inner: { flex: 1, padding: 20, gap: 16, width: '100%', maxWidth: 560, alignSelf: 'center' },
  title: { fontSize: 30, fontWeight: '800', letterSpacing: -0.5 },
  body: { fontSize: 16, lineHeight: 23 },
  label: { fontSize: 14, fontWeight: '600' },
  input: { borderWidth: 1, borderRadius: radius, paddingHorizontal: 14, paddingVertical: 13, fontSize: 17 },
  button: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, minHeight: 50,
    borderRadius: radius, paddingHorizontal: 18, borderWidth: StyleSheet.hairlineWidth,
  },
  buttonText: { fontSize: 17, fontWeight: '600' },
  card: { borderWidth: StyleSheet.hairlineWidth, borderRadius: radius + 2, overflow: 'hidden' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 16, paddingVertical: 12, minHeight: 56 },
  rowTitle: { fontSize: 16, fontWeight: '500' },
  rowSub: { fontSize: 13, marginTop: 2 },
  search: { flexDirection: 'row', alignItems: 'center', gap: 10, borderWidth: 1, borderRadius: radius, paddingHorizontal: 14 },
  fab: {
    position: 'absolute', right: 20, flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 20, height: 54,
    borderRadius: 27, shadowColor: '#000', shadowOpacity: 0.35, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 6,
  },
  notice: { flexDirection: 'row', gap: 10, borderWidth: 1, borderRadius: radius, padding: 12, alignItems: 'flex-start' },
});

export function ProgressBar({ value, color }: { value: number; color?: string }) {
  const c = useColors();
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: 100, now: Math.round(pct) }}
      style={{ height: 6, borderRadius: 3, backgroundColor: c.surface2, overflow: 'hidden' }}>
      <View style={{ width: `${pct}%`, height: '100%', backgroundColor: color ?? c.accent }} />
    </View>
  );
}

/** WiFiDrop's mark: the white arrow on blue. */
export function Logo({ size = 40 }: { size?: number }) {
  return (
    <Image source={require('@/assets/images/icon.png')} style={{ width: size, height: size, borderRadius: size * 0.25 }}
      accessibilityLabel="WiFiDrop" />
  );
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  const c = useColors();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 4 }}>
      <Text accessibilityRole="header" style={{ color: c.muted, fontWeight: '700', fontSize: 13, letterSpacing: 0.6, flex: 1 }}>{children}</Text>
      {right}
    </View>
  );
}

export function SearchField({ value, onChangeText, placeholder }: { value: string; onChangeText: (t: string) => void; placeholder: string }) {
  const c = useColors();
  return (
    <View style={[styles.search, { backgroundColor: c.surface, borderColor: c.border }]}>
      <Ionicons name="search" size={18} color={c.muted} />
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={c.muted}
        accessibilityLabel={placeholder}
        autoCapitalize="none"
        autoCorrect={false}
        returnKeyType="search"
        clearButtonMode="never"
        style={{ flex: 1, color: c.text, fontSize: 16, paddingVertical: 11 }}
      />
      {value ? (
        <Pressable accessibilityRole="button" accessibilityLabel="Clear search" hitSlop={10} onPress={() => onChangeText('')}>
          <Ionicons name="close-circle" size={18} color={c.muted} />
        </Pressable>
      ) : null}
    </View>
  );
}

/** The round blue button in the corner. */
export function Fab({ icon, label, onPress, bottom = 24 }: { icon: IconName; label: string; onPress: () => void; bottom?: number }) {
  const c = useColors();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [styles.fab, { backgroundColor: c.accent, bottom, transform: [{ scale: pressed ? 0.96 : 1 }] }]}>
      <Ionicons name={icon} size={22} color={c.accentInk} />
      <Text style={{ color: c.accentInk, fontWeight: '700', fontSize: 16 }}>{label}</Text>
    </Pressable>
  );
}

export function SwitchRow({ icon, title, subtitle, value, onValueChange }: {
  icon: IconName; title: string; subtitle?: string; value: boolean; onValueChange: (v: boolean) => void;
}) {
  const c = useColors();
  return (
    <View style={styles.row}>
      <Ionicons name={icon} size={26} color={c.accent} />
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={[styles.rowTitle, { color: c.text }]}>{title}</Text>
        {subtitle ? <Text style={[styles.rowSub, { color: c.muted }]}>{subtitle}</Text> : null}
      </View>
      <Switch value={value} onValueChange={onValueChange} trackColor={{ true: c.accent, false: c.surface2 }} accessibilityLabel={title} />
    </View>
  );
}
