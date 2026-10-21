import Constants from 'expo-constants';
import { Redirect, router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { Alert, Platform, Text, View } from 'react-native';

import { useSession } from '@/state/session';
import { Body, Button, Card, Row, Screen, Separator } from '@/ui/kit';
import { useColors } from '@/ui/theme';

export default function Settings() {
  const c = useColors();
  const { pc, me, signOut, forget } = useSession();

  async function doSignOut() {
    await signOut();
    router.dismissAll();
    router.replace('/sign-in');
  }

  function confirmForget() {
    if (!pc) return;
    const go = async () => {
      await forget(pc.serverId);
      router.dismissAll();
      router.replace('/');
    };
    if (Platform.OS === 'web') return go();
    Alert.alert(`Forget ${pc.name}?`, 'You will need to scan its QR code again to connect. Your files stay on the PC.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Forget', style: 'destructive', onPress: go },
    ]);
  }

  if (!pc) return <Redirect href="/" />;
  const pro = me?.edition === 'pro';
  return (
    <Screen>
      <View style={{ gap: 8 }}>
        <Text style={{ color: c.muted, fontWeight: '600' }}>THIS PC</Text>
        <Card>
          <Row icon="desktop" title={pc.name} subtitle={pc.demo ? 'Demo' : `${pc.host}:${pc.port}`} />
          <Separator />
          <Row icon="person" title={me ? me.user.display_name || me.user.username : pc.username ?? ''}
            subtitle={me ? `WiFiDrop ${me.version} on the PC` : undefined} />
          <Separator />
          <Row icon={pro ? 'star' : 'star-outline'} iconColor={pro ? c.warn : c.muted} title={pro ? 'WiFiDrop Pro' : 'WiFiDrop Free'}
            subtitle={pro ? 'Pro features are on' : 'Pro on the PC unlocks auto-upload'} />
          <Separator />
          <Row icon="swap-horizontal" title="Switch or add a PC" onPress={() => router.push('/connect')} />
        </Card>
      </View>
      <Button title="Sign out" kind="secondary" icon="log-out-outline" onPress={doSignOut} />
      <Button title="Forget this PC" kind="danger" icon="trash-outline" onPress={confirmForget} />
      <View style={{ gap: 8 }}>
        <Text style={{ color: c.muted, fontWeight: '600' }}>ABOUT</Text>
        <Card>
          <Row icon="shield-checkmark" title="Privacy" subtitle="The app talks only to your PC"
            onPress={() => WebBrowser.openBrowserAsync('https://wifidrop.ca/privacy.html')} />
          <Separator />
          <Row icon="help-circle" title="Help" onPress={() => WebBrowser.openBrowserAsync('https://wifidrop.ca/guide.html')} />
        </Card>
      </View>
      <Body muted center>WiFiDrop {Constants.expoConfig?.version} · No accounts, no tracking, no cloud.</Body>
    </Screen>
  );
}
