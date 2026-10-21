import { router } from 'expo-router';
import { useState } from 'react';

import { ApiError } from '@/api/types';
import { useSession } from '@/state/session';
import { Body, Button, Field, Notice, Screen, Title } from '@/ui/kit';

/** First sign-in with a password the PC's owner chose: pick your own before going on. */
export default function NewPassword() {
  const { client, setMe, signOut } = useSession();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [again, setAgain] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (next !== again) {
      setError("The new passwords don't match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setMe(await client!.changePassword(current, next));
      router.replace('/files');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Title>Choose your password</Title>
      <Body muted>You signed in with a password someone else chose. Pick one only you know.</Body>
      <Field label="Current password" value={current} onChangeText={setCurrent} secureTextEntry textContentType="password" />
      <Field label="New password" value={next} onChangeText={setNext} secureTextEntry textContentType="newPassword"
        autoComplete="new-password" />
      <Field label="New password again" value={again} onChangeText={setAgain} secureTextEntry textContentType="newPassword"
        onSubmitEditing={submit} />
      <Notice text={error} />
      <Button title="Save password" onPress={submit} busy={busy} />
      <Button title="Sign out" kind="secondary" onPress={async () => { await signOut(); router.replace('/sign-in'); }} />
    </Screen>
  );
}
