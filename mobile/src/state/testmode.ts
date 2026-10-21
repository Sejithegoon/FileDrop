// Expo Go test mode (see src/api/http.ts): connect to a PC over plain HTTP by its address.
import { Client } from '@/api/client';
import { HttpTransport } from '@/api/http';
import { ApiError } from '@/api/types';
import { WifidropNet } from '@modules/wifidrop-net';

import type { SavedPc } from './store';

/** True inside Expo Go (and the web preview), where the app's own secure networking isn't available. */
export const testModeOnly = !WifidropNet;

export const HTTPS_OFF_HINT =
  'Expo Go can only test over plain HTTP. On your PC, open WiFiDrop and turn off "Secure connection (HTTPS)" on the Dashboard, then try again. Turn it back on when you finish testing.';

export async function testModePc(host: string, port: number): Promise<SavedPc> {
  const info = await new Client(new HttpTransport(`http://${host}:${port}`)).info();
  if (!info.server_id) throw new ApiError(0, 'PC_TOO_OLD', 'Update WiFiDrop on your PC to 0.2 or newer.');
  return { serverId: info.server_id, name: info.name, host, port, pin: '', insecure: true };
}
