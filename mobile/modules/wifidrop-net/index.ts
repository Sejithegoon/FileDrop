// Pinned HTTPS and network discovery, implemented in Swift (ios/) and Kotlin (android/).
import { requireOptionalNativeModule } from 'expo';

type EventSubscription = { remove(): void };

export type NetRequest = {
  url: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  bodyFile?: string;
  bodyOffset?: number;
  bodyLength?: number;
  pin: string;
  timeoutMs?: number;
};

export type NetResponse = { status: number; headers: Record<string, string>; body: string };
export type ProbeResult = { pin: string; status: number; body: string };
export type DownloadRequest = { id: string; url: string; headers?: Record<string, string>; destination: string; pin: string };
export type DownloadResult = { status: number; uri?: string; bytes?: number; body?: string };
export type FoundService = { name: string; txt: Record<string, string> };

type Events = {
  onProgress(e: { id: string; written: number; total: number }): void;
  onServiceFound(e: FoundService): void;
  onServiceLost(e: { name: string }): void;
  onDiscoveryError(e: { message: string }): void;
};

type NativeModule = {
  request(o: NetRequest): Promise<NetResponse>;
  probe(url: string): Promise<ProbeResult>;
  download(o: DownloadRequest): Promise<DownloadResult>;
  startDiscovery(): void;
  stopDiscovery(): void;
  addListener<K extends keyof Events>(name: K, listener: Events[K]): EventSubscription;
};

/** null on the web and in Expo Go, where the app only runs its demo. */
export const WifidropNet = requireOptionalNativeModule<NativeModule>('WifidropNet');
