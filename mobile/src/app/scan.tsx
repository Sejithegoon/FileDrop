import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { Client } from '@/api/client';
import { PinnedTransport } from '@/api/transport';
import { ApiError } from '@/api/types';
import { baseUrl, isPlainWiFiDropLink, parsePairingQr } from '@/lib/pairing';
import { useSession } from '@/state/session';
import { Body, Button, Loading, Notice, Screen, Title } from '@/ui/kit';
import { radius, useColors } from '@/ui/theme';

export default function Scan() {
  const c = useColors();
  const { pair } = useSession();
  const [permission, requestPermission] = useCameraPermissions();
  const [message, setMessage] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const lastText = useRef('');

  async function onScanned(text: string) {
    if (checking || text === lastText.current) return;
    lastText.current = text;
    const pairing = parsePairingQr(text);
    if (!pairing) {
      setMessage(isPlainWiFiDropLink(text)
        ? 'This PC needs WiFiDrop 0.2 or newer with HTTPS turned on. Update WiFiDrop on your PC, then scan again.'
        : "That isn't a WiFiDrop code. Scan the QR code on the Dashboard of WiFiDrop on your PC.");
      return;
    }
    setChecking(true);
    setMessage(null);
    try {
      // Connect trusting only the key from the code, and make sure it's the same PC.
      const info = await new Client(new PinnedTransport(baseUrl(pairing), pairing.pin)).info();
      if (info.server_id !== pairing.serverId) throw new ApiError(0, 'WRONG_PC', "That code belongs to a different PC.");
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      await pair({ serverId: info.server_id, name: info.name, host: pairing.host, port: pairing.port, pin: pairing.pin });
      router.dismissTo('/sign-in');
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : 'Something went wrong. Try again.');
      lastText.current = ''; // allow scanning the same code again
    } finally {
      setChecking(false);
    }
  }

  if (!permission) return <Loading />;

  if (!permission.granted) {
    return (
      <Screen>
        <Title>Camera</Title>
        <Body>WiFiDrop uses the camera only to read the QR code on your PC's screen.</Body>
        {permission.canAskAgain ? (
          <Button title="Allow camera" icon="camera" onPress={requestPermission} />
        ) : (
          <Notice kind="warn" text="Camera access is off. Turn it on for WiFiDrop in your phone's Settings." />
        )}
      </Screen>
    );
  }

  return (
    <Screen scroll={false}>
      <Body muted>Point your camera at the QR code on WiFiDrop's Dashboard on your PC.</Body>
      <View style={[styles.frame, { borderColor: c.accent }]}>
        <CameraView
          style={StyleSheet.absoluteFill}
          facing="back"
          barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
          onBarcodeScanned={checking ? undefined : (r) => onScanned(r.data)}
        />
      </View>
      {checking ? <Notice kind="ok" text="Connecting to your PC…" /> : <Notice text={message} />}
    </Screen>
  );
}

const styles = StyleSheet.create({
  frame: { aspectRatio: 1, width: '100%', borderRadius: radius, overflow: 'hidden', borderWidth: 2 },
});
