// Run: deno test supabase/functions/payments
import type { Keys, LicenceRow, Mailer } from "../licence/logic.ts";
import { PermanentMailError, readLicence } from "../licence/logic.ts";
import { type Config, handle, type Paddle, type PaymentStore, signHeader } from "./logic.ts";

function assert(cond: unknown, msg = "assertion failed"): asserts cond { if (!cond) throw new Error(msg); }

const SECRET = "pdl_ntfset_test_secret";
const PRICE = "pri_filedrop_pro";

async function testKeys(): Promise<Keys> {
  const pair = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]) as CryptoKeyPair;
  return {
    sign: async (d) => new Uint8Array(await crypto.subtle.sign("Ed25519", pair.privateKey, d.slice())),
    verify: (s, d) => crypto.subtle.verify("Ed25519", pair.publicKey, s.slice(), d.slice()),
  };
}

type Row = LicenceRow & { note: string; order_id: string | null; revoke_reason?: string };

class MemoryStore implements PaymentStore {
  events = new Map<string, string>();
  licences: Row[] = [];
  failInsertOnce = false;
  countHits() { return Promise.resolve(0); }
  addHit() { return Promise.resolve(); }
  getLicence(id: string) { return Promise.resolve(this.licences.find((l) => l.id === id) ?? null); }
  licencesByEmail(e: string) { return Promise.resolve(this.licences.filter((l) => l.email === e)); }
  insertLicence(row: Row) {
    if (this.failInsertOnce) { this.failInsertOnce = false; return Promise.reject(new Error("db down")); }
    if (row.order_id && this.licences.some((l) => l.order_id === row.order_id)) return Promise.reject(new Error("duplicate order"));
    this.licences.push(row); return Promise.resolve();
  }
  activations() { return Promise.resolve([]); }
  addActivation() { return Promise.resolve(); }
  touchActivation() { return Promise.resolve(); }
  removeActivation() { return Promise.resolve(); }
  isAdmin() { return Promise.resolve(false); }
  seenEvent(id: string) { return Promise.resolve(this.events.has(id)); }
  recordEvent(id: string, _t: string, result: string) { this.events.set(id, result); return Promise.resolve(); }
  licenceByOrder(o: string) { return Promise.resolve(this.licences.find((l) => l.order_id === o) ?? null); }
  setRevoked(o: string, at: string | null, reason: string) {
    const rows = this.licences.filter((l) => l.order_id === o);
    rows.forEach((l) => { l.revoked_at = at; l.revoke_reason = reason; });
    return Promise.resolve(rows.length);
  }
}

class Mail implements Mailer {
  sent: { to: string; text: string }[] = [];
  send(to: string, _s: string, text: string) { this.sent.push({ to, text }); return Promise.resolve(); }
}

const paddle: Paddle = { customerEmail: (id) => Promise.resolve(id === "ctm_sam" ? "Sam@Example.com" : "") };
const NOW = Date.parse("2026-10-18T12:00:00Z");
const cfg: Config = {
  webhookSecret: SECRET, priceIds: [PRICE], sandbox: true, updatesMonths: 12, maxActivations: 3, toleranceSec: 300,
  licence: { allowedOrigins: [], ipSalt: "", rateLimit: 0, resendLimit: 0, rateWindowMs: 0, defaultUpdatesMonths: 12, websiteUrl: "https://example.test" },
};

async function webhook(event: Record<string, unknown>, opts: { secret?: string; ts?: number } = {}) {
  const raw = JSON.stringify(event);
  const sig = await signHeader(opts.secret ?? SECRET, raw, opts.ts ?? Math.floor(NOW / 1000));
  return new Request("https://x.supabase.co/functions/v1/payments", { method: "POST", body: raw, headers: { "paddle-signature": sig } });
}

const paid = (eventId = "evt_1", txn = "txn_1", price = PRICE) => ({
  event_id: eventId, event_type: "transaction.completed",
  data: { id: txn, status: "completed", customer_id: "ctm_sam", items: [{ price: { id: price } }] },
});
const adjustment = (eventId: string, action: string, status = "approved", type = "full") => ({
  event_id: eventId, event_type: "adjustment.updated", data: { id: "adj_1", action, status, type, transaction_id: "txn_1" },
});

Deno.test("purchase issues one licence and emails it, even if Paddle sends the event twice", async () => {
  const keys = await testKeys(); const s = new MemoryStore(); const mail = new Mail();
  const r = await handle(await webhook(paid()), s, keys, paddle, mail, cfg, NOW);
  assert(r.status === 200, `status ${r.status}`);
  assert(s.licences.length === 1 && s.licences[0].email === "sam@example.com" && s.licences[0].order_id === "txn_1");
  assert(s.licences[0].updates_until === "2027-10-18" && s.licences[0].note.includes("sandbox"));
  const payload = await readLicence(keys, s.licences[0].licence_text);
  assert(payload?.lid === s.licences[0].id && payload?.max === 3);
  assert(mail.sent.length === 1 && mail.sent[0].text.includes(s.licences[0].licence_text));
  const again = await (await handle(await webhook(paid()), s, keys, paddle, mail, cfg, NOW)).json();
  assert(again.duplicate === true && s.licences.length === 1 && mail.sent.length === 1);
  // A different event for the same order (e.g. replayed by support) still doesn't make a second licence.
  await handle(await webhook(paid("evt_2")), s, keys, paddle, mail, cfg, NOW);
  assert(s.licences.length === 1);
});

Deno.test("bad, missing, old or foreign signatures are refused", async () => {
  const keys = await testKeys(); const s = new MemoryStore();
  assert((await handle(await webhook(paid(), { secret: "wrong" }), s, keys, paddle, null, cfg, NOW)).status === 401);
  assert((await handle(await webhook(paid(), { ts: Math.floor(NOW / 1000) - 3600 }), s, keys, paddle, null, cfg, NOW)).status === 401);
  const raw = JSON.stringify(paid());
  assert((await handle(new Request("https://x/payments", { method: "POST", body: raw }), s, keys, paddle, null, cfg, NOW)).status === 401);
  const tampered = new Request("https://x/payments", { method: "POST", body: raw.replace("ctm_sam", "ctm_eve"),
    headers: { "paddle-signature": await signHeader(SECRET, raw, Math.floor(NOW / 1000)) } });
  assert((await handle(tampered, s, keys, paddle, null, cfg, NOW)).status === 401);
  assert((await handle(await webhook(paid()), s, keys, paddle, null, { ...cfg, webhookSecret: "" }, NOW)).status === 401);
  assert(s.licences.length === 0);
});

Deno.test("other products don't issue licences", async () => {
  const keys = await testKeys(); const s = new MemoryStore();
  const body = await (await handle(await webhook(paid("evt_9", "txn_9", "pri_other")), s, keys, paddle, null, cfg, NOW)).json();
  assert(body.result.startsWith("ignored") && s.licences.length === 0);
});

Deno.test("full refund and chargeback revoke; partial refund and pending don't; reversal restores", async () => {
  const keys = await testKeys(); const s = new MemoryStore();
  await handle(await webhook(paid()), s, keys, paddle, null, cfg, NOW);
  await handle(await webhook(adjustment("evt_a", "refund", "pending_approval")), s, keys, paddle, null, cfg, NOW);
  await handle(await webhook(adjustment("evt_b", "refund", "approved", "partial")), s, keys, paddle, null, cfg, NOW);
  assert(s.licences[0].revoked_at === null, "still active");
  await handle(await webhook(adjustment("evt_c", "refund")), s, keys, paddle, null, cfg, NOW);
  assert(s.licences[0].revoked_at && s.licences[0].revoke_reason === "refund");
  await handle(await webhook(adjustment("evt_d", "chargeback_reverse")), s, keys, paddle, null, cfg, NOW);
  assert(s.licences[0].revoked_at === null);
  await handle(await webhook(adjustment("evt_e", "chargeback")), s, keys, paddle, null, cfg, NOW);
  assert((s.licences[0].revoke_reason as string) === "chargeback");
});

Deno.test("a refused email is recorded instead of retried forever", async () => {
  const keys = await testKeys(); const s = new MemoryStore();
  const refusing: Mailer = { send: () => Promise.reject(new PermanentMailError("email: 403 not allowed")) };
  const r = await handle(await webhook(paid()), s, keys, paddle, refusing, cfg, NOW);
  assert(r.status === 200 && s.licences.length === 1);
  assert(s.events.get("evt_1")!.includes("EMAIL FAILED"));
});

Deno.test("refunding the product line in full revokes, even when the transaction refund is partial", async () => {
  const keys = await testKeys(); const s = new MemoryStore();
  await handle(await webhook(paid()), s, keys, paddle, null, cfg, NOW);
  const partialAmount = { event_id: "evt_p", event_type: "adjustment.updated",
    data: { action: "refund", status: "approved", type: "partial", transaction_id: "txn_1", items: [{ type: "partial" }] } };
  const body = await (await handle(await webhook(partialAmount), s, keys, paddle, null, cfg, NOW)).json();
  assert(s.licences[0].revoked_at === null && body.result.includes("kept licence"));
  const fullLine = { event_id: "evt_f", event_type: "adjustment.updated",
    data: { action: "refund", status: "approved", type: "partial", transaction_id: "txn_1", items: [{ type: "full" }] } };
  await handle(await webhook(fullLine), s, keys, paddle, null, cfg, NOW);
  assert(s.licences[0].revoked_at !== null);
});

Deno.test("a failure returns 500 so Paddle retries, and the retry completes", async () => {
  const keys = await testKeys(); const s = new MemoryStore(); const mail = new Mail();
  s.failInsertOnce = true;
  assert((await handle(await webhook(paid()), s, keys, paddle, mail, cfg, NOW)).status === 500);
  assert(!s.events.has("evt_1") && s.licences.length === 0);
  assert((await handle(await webhook(paid()), s, keys, paddle, mail, cfg, NOW)).status === 200);
  assert((s.licences.length as number) === 1 && mail.sent.length === 1);
});
