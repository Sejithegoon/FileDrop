// Paddle webhooks: a completed purchase issues and emails a Pro licence; a full refund or a
// chargeback revokes it (the app turns Pro read-only at its next check-in).
// Every event is handled once: repeats are recognised by event ID, and licences by order ID.
import {
  addMonths, type Config as LicenceConfig, issueLicence, type Keys, type LicenceRow, type LicenceStore, type Mailer, sendLicences,
  PermanentMailError,
} from "../licence/logic.ts";

export interface PaymentStore extends LicenceStore {
  seenEvent(id: string): Promise<boolean>;
  recordEvent(id: string, type: string, result: string): Promise<void>;
  licenceByOrder(orderId: string): Promise<LicenceRow | null>;
  setRevoked(orderId: string, revokedAt: string | null, reason: string): Promise<number>;
}

export interface Paddle {
  customerEmail(customerId: string): Promise<string>;
}

export interface Config {
  webhookSecret: string;
  priceIds: string[]; // only these prices issue a Pro licence
  sandbox: boolean;
  updatesMonths: number;
  maxActivations: number;
  toleranceSec: number;
  licence: LicenceConfig;
  /** Paddle's current webhook IPs as CIDRs, or null if they couldn't be fetched (the signature still protects). */
  paddleIps?: () => Promise<string[] | null>;
}

const enc = new TextEncoder();

function ipv4(ip: string): number | null {
  const m = ip.trim().match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!m) return null;
  const parts = m.slice(1).map(Number);
  return parts.some((n) => n > 255) ? null : ((parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]) >>> 0;
}

/** True if the IPv4 address is inside one of the CIDR ranges (Paddle publishes /32s). */
export function ipAllowed(ip: string, cidrs: string[]): boolean {
  const addr = ipv4(ip);
  if (addr === null) return false;
  return cidrs.some((c) => {
    const [base, bits = "32"] = c.split("/");
    const net = ipv4(base), n = Number(bits);
    if (net === null || !(n >= 0 && n <= 32)) return false;
    const mask = n === 0 ? 0 : (0xffffffff << (32 - n)) >>> 0;
    return ((addr & mask) >>> 0) === ((net & mask) >>> 0);
  });
}

async function hmacHex(secret: string, message: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(message)));
  return [...sig].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/** Paddle-Signature: "ts=1700000000;h1=<hex>" over "<ts>:<raw body>". */
export async function verifySignature(header: string, raw: string, secret: string, nowSec: number, toleranceSec: number) {
  const parts = Object.fromEntries(header.split(";").map((p) => p.split("=", 2) as [string, string]));
  const ts = Number(parts.ts);
  if (!secret || !ts || !parts.h1 || Math.abs(nowSec - ts) > toleranceSec) return false;
  const expected = await hmacHex(secret, `${parts.ts}:${raw}`);
  return header.split(";").filter((p) => p.startsWith("h1=")).some((p) => safeEqual(p.slice(3), expected));
}

export function signHeader(secret: string, raw: string, ts: number): Promise<string> {
  return hmacHex(secret, `${ts}:${raw}`).then((h) => `ts=${ts};h1=${h}`);
}

type Event = { event_id: string; event_type: string; data: Record<string, any> };

export async function handle(req: Request, store: PaymentStore, keys: Keys, paddle: Paddle, mailer: Mailer | null,
  cfg: Config, now = Date.now()): Promise<Response> {
  const reply = (status: number, body: Record<string, unknown>) =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  if (req.method !== "POST") return reply(405, { ok: false });
  if (cfg.paddleIps) {
    const cidrs = await cfg.paddleIps();
    const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
    if (cidrs && !ipAllowed(ip, cidrs)) return reply(403, { ok: false, error: "not from Paddle" });
  }
  const raw = await req.text();
  if (!(await verifySignature(req.headers.get("paddle-signature") || "", raw, cfg.webhookSecret, Math.floor(now / 1000), cfg.toleranceSec))) {
    return reply(401, { ok: false, error: "bad signature" });
  }
  let ev: Event;
  try {
    ev = JSON.parse(raw);
  } catch {
    return reply(400, { ok: false, error: "bad json" });
  }
  if (!ev.event_id || !ev.event_type || !ev.data) return reply(400, { ok: false, error: "not an event" });
  if (await store.seenEvent(ev.event_id)) return reply(200, { ok: true, duplicate: true });

  try {
    const result = await process(ev, store, keys, paddle, mailer, cfg, now);
    await store.recordEvent(ev.event_id, ev.event_type, result);
    return reply(200, { ok: true, result });
  } catch (err) {
    // 500 makes Paddle retry later; nothing is recorded, and order IDs stop a second licence.
    console.error("payments error", ev.event_type, err);
    return reply(500, { ok: false, error: "will retry" });
  }
}

async function process(ev: Event, store: PaymentStore, keys: Keys, paddle: Paddle, mailer: Mailer | null,
  cfg: Config, now: number): Promise<string> {
  const d = ev.data;
  if (ev.event_type === "transaction.completed") {
    const prices: string[] = (d.items || []).map((i: any) => i?.price?.id).filter(Boolean);
    if (!prices.some((p) => cfg.priceIds.includes(p))) return "ignored: not WiFiDrop Pro";
    let lic = await store.licenceByOrder(d.id);
    if (!lic) {
      const email = (await paddle.customerEmail(d.customer_id)).trim().toLowerCase();
      if (!email) throw new Error(`no email for customer ${d.customer_id}`);
      lic = await issueLicence(store, keys, {
        email, updatesUntil: addMonths(new Date(now), cfg.updatesMonths), max: cfg.maxActivations, orderId: d.id, now,
        note: cfg.sandbox ? "Paddle sandbox test purchase" : "Paddle",
      });
    }
    if (!mailer) return `licence ${lic.id} (no email service set)`;
    try {
      await sendLicences(mailer, cfg.licence.websiteUrl, lic.email, [lic]);
    } catch (err) {
      // A refused email won't succeed on retry: keep the licence, record why, and send it from the inbox.
      if (err instanceof PermanentMailError) return `licence ${lic.id} issued, EMAIL FAILED: ${err.message}`;
      throw err;
    }
    return `licence ${lic.id} emailed`;
  }
  if (ev.event_type === "adjustment.created" || ev.event_type === "adjustment.updated") {
    if (d.status !== "approved" || !d.transaction_id) return `ignored: adjustment ${d.status}`;
    // Paddle marks each refunded line: "full" means that product was refunded completely, even if
    // the transaction total differs (for example a rounding or tax difference).
    const lines: string = (d.items || []).map((i: any) => i?.type).filter(Boolean).join(",") || "none";
    const productRefunded = d.type === "full" || (d.items || []).some((i: any) => i?.type === "full");
    if (d.action === "chargeback" || (d.action === "refund" && productRefunded)) {
      const n = await store.setRevoked(d.transaction_id, new Date(now).toISOString(), d.action);
      return `revoked ${n} licence(s): ${d.action} (${d.type || "?"}; lines ${lines})`;
    }
    if (d.action === "refund") return `kept licence: partial refund (lines ${lines})`;
    if (d.action === "chargeback_reverse") {
      const n = await store.setRevoked(d.transaction_id, null, "");
      return `restored ${n} licence(s)`;
    }
    return `ignored: ${d.action} ${d.type || ""}`.trim();
  }
  return "ignored";
}
