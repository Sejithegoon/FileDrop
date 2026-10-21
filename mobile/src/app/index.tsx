import { Redirect } from 'expo-router';

import { useSession } from '@/state/session';
import { Loading } from '@/ui/kit';

/** Opens where the person left off: pairing, signing in, or their files. */
export default function Start() {
  const { ready, pc, signedIn } = useSession();
  if (!ready) return <Loading />;
  if (!pc) return <Redirect href="/connect" />;
  if (!signedIn) return <Redirect href="/sign-in" />;
  return <Redirect href="/files" />;
}
