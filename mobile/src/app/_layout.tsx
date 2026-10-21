import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useColorScheme } from 'react-native';

import { SessionProvider } from '@/state/session';
import { UploadKeeper } from '@/uploads/keeper';
import { useColors } from '@/ui/theme';

export default function RootLayout() {
  const scheme = useColorScheme();
  const c = useColors();
  const base = scheme === 'light' ? DefaultTheme : DarkTheme;
  const theme = { ...base, colors: { ...base.colors, background: c.bg, card: c.bg, text: c.text, border: c.border, primary: c.accent } };
  return (
    <ThemeProvider value={theme}>
      <SessionProvider>
        <StatusBar style={scheme === 'light' ? 'dark' : 'light'} />
        <UploadKeeper />
        <Stack screenOptions={{ headerTintColor: c.accent, headerTitleStyle: { color: c.text }, headerShadowVisible: false }}>
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="connect" options={{ title: 'Connect' }} />
          <Stack.Screen name="scan" options={{ title: 'Scan QR code', presentation: 'modal' }} />
          <Stack.Screen name="confirm" options={{ title: 'Check the code' }} />
          <Stack.Screen name="sign-in" options={{ title: 'Sign in' }} />
          <Stack.Screen name="password" options={{ title: 'New password', headerBackVisible: false }} />
          <Stack.Screen name="files/index" options={{ title: 'WiFiDrop', headerBackVisible: false }} />
          <Stack.Screen name="files/[space]" options={{ title: '' }} />
          <Stack.Screen name="settings" options={{ title: 'Settings' }} />
          <Stack.Screen name="uploads" options={{ title: 'Uploads' }} />
          <Stack.Screen name="view" options={{ title: '' }} />
        </Stack>
      </SessionProvider>
    </ThemeProvider>
  );
}
