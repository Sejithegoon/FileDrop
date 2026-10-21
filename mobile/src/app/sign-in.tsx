import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';

import { ApiError } from '@/api/types';
import { useSession } from '@/state/session';
import { Body, Button, Field, Logo, Notice, Screen, Title } from '@/ui/kit';
import { useColors } from '@/ui/theme';

export default function SignIn() {
  const c = useColors();
  const { pc, signIn, client } = useSession();
  const [username, setUsername] = useState(pc?.username ?? '');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!pc) router.replace('/connect');
  }, [pc]);

  // Say early if the PC's WiFiDrop is too old for the app, instead of after typing a password.
  useEffect(() => {
    client?.info().catch((e) => {
      if (e instanceof ApiError && e.code === 'APP_TOO_OLD') setError(e.message);
    });
  }, [client]);

  async function submit() {
    if (!username.trim() || !password) {
      setError('Enter your username and password.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const me = await signIn(username, password);
      router.replace(me.user.must_change_password ? '/password' : '/files');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Try again.');
    } finally {
      setBusy(false);
    }
  }

  if (!pc) return null;
  return (
    <Screen>
      <View style={{ alignItems: 'center', paddingTop: 8 }}>
        <Logo size={64} />
      </View>
      <Title>Sign in</Title>
      <Body muted>
        To <Text style={{ color: c.text, fontWeight: '600' }}>{pc.name}</Text>, with the account the PC's owner made for you.
      </Body>
      {pc.demo && <Notice kind="ok" text='This is the demo. Sign in with username "demo" and password "demo".' />}
      <Field label="Username" value={username} onChangeText={setUsername} textContentType="username" autoComplete="username"
        returnKeyType="next" />
      <Field label="Password" value={password} onChangeText={setPassword} secureTextEntry textContentType="password"
        autoComplete="current-password" returnKeyType="go" onSubmitEditing={submit} />
      <Notice text={error} />
      <Button title="Sign in" onPress={submit} busy={busy} />
      <Button title="Use a different PC" kind="secondary" onPress={() => router.push('/connect')} />
      <Body muted center>Forgot your password? Ask the person who runs WiFiDrop on the PC to reset it.</Body>
    </Screen>
  );
}
