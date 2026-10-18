// Run: deno test supabase/functions/licence
import { b64url, type Config, handle, type Keys, type LicenceRow, type LicenceStore, type Mailer, readLicence } from "./logic.ts";

function assert(cond: unknown, msg = "assertion failed"): asserts cond { if (!cond) throw new Error(msg); }

async function testKeys(): Promise<{ keys: Keys; publicB64: string }> {
  const pair = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]) as CryptoKeyPair;
  const raw = new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey));
  return {
    keys: {
      sign: async (d) => new Uint8Array(await crypto.subtle.sign("Ed25519", pair.privateKey, d.slice())),
      verify: (s, d) => crypto.subtle.verify("Ed25519", pair.publicKey, s.slice(), d.slice()),
    },
    publicB64: btoa(String.fromCharCode(...raw)),
  };
}

class MemoryStore implements LicenceStore {
  hits: { key: string; at: number }[] = [];
  licences = new Map<string, LicenceRow & { note: string; order_id: string | null }>();
  acts = new Map<string, Set<string>>();
  admins = new Set(["Bearer admin-token"]);
  countHits(key: string, since: number) { return Promise.resolve(this.hits.filter((h) => h.key === key && h.at > since).length); }
  addHit(key: string) { this.hits.push({ key, at: Date.now() }); return Promise.resolve(); }
  getLicence(id: string) { return Promise.resolve(this.licences.get(id) ?? null); }
  licencesByEmail(email: string) { return Promise.resolve([...this.licences.values()].filter((l) => l.email === email)); }
  insertLicence(row: LicenceRow & { note: string; order_id: string | null }) { this.licences.set(row.id, row); return Promise.resolve(); }
  activations(id: string) { return Promise.resolve([...(this.acts.get(id) ?? [])]); }
  addActivation(id: string, iid: string) { (this.acts.get(id) ?? this.acts.set(id, new Set()).get(id)!).add(iid); return Promise.resolve(); }
  touchActivation() { return Promise.resolve(); }
  removeActivation(id: string, iid: string) { this.acts.get(id)?.delete(iid); return Promise.resolve(); }
  isAdmin(auth: string) { return Promise.resolve(this.admins.has(auth)); }
}

class MemoryMailer implements Mailer {
  sent: { to: string; text: string }[] = [];
  send(to: string, _s: string, text: string) { this.sent.push({ to, text }); return Promise.resolve(); }
}

const cfg: Config = {
  allowedOrigins: ["https://sejithegoon.github.io"], ipSalt: "salt", rateLimit: 30, resendLimit: 3,
  rateWindowMs: 600000, defaultUpdatesMonths: 12, websiteUrl: "https://example.test",
};

function post(route: string, body: unknown, headers: Record<string, string> = {}, ip = "1.2.3.4") {
  return new Request(`https://x.supabase.co/functions/v1/licence/${route}`, {
    method: "POST", body: JSON.stringify(body), headers: { "content-type": "application/json", "x-forwarded-for": ip, ...headers },
  });
}

async function statusOf(keys: Keys, r: Response) {
  const body = await r.json();
  const [p, s] = body.status.split(".");
  const dec = (x: string) => Uint8Array.from(atob(x.replaceAll("-", "+").replaceAll("_", "/")), (c) => c.charCodeAt(0));
  assert(await keys.verify(dec(s), dec(p)), "status signature");
  return JSON.parse(new TextDecoder().decode(dec(p)));
}

async function issue(store: MemoryStore, keys: Keys, extra: Record<string, unknown> = {}, mailer?: Mailer) {
  const r = await handle(post("issue", { email: "Sam@Example.com", ...extra }, { authorization: "Bearer admin-token" }),
    store, keys, cfg, { mailer, now: Date.parse("2026-10-16T00:00:00Z") });
  assert(r.status === 200, `issue ${r.status}`);
  return await r.json();
}

Deno.test("only admins can issue; licence verifies and has a year of updates", async () => {
  const { keys } = await testKeys();
  const s = new MemoryStore();
  const denied = await handle(post("issue", { email: "a@b.co" }, { authorization: "Bearer someone" }), s, keys, cfg);
  assert(denied.status === 401);
  const lic = await issue(s, keys, { note: "test" });
  assert(/^FDP-[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}$/.test(lic.id), lic.id);
  const payload = await readLicence(keys, lic.licence);
  assert(payload && payload.lid === lic.id && payload.to === "sam@example.com" && payload.upd === "2027-10-16" && payload.max === 3);
  assert(s.licences.get(lic.id)!.note === "test");
});

Deno.test("activate up to 3 PCs, then limit; same PC again is fine", async () => {
  const { keys } = await testKeys();
  const s = new MemoryStore();
  const { licence } = await issue(s, keys);
  for (const pc of ["pc-aaaaaaaa", "pc-bbbbbbbb", "pc-cccccccc", "pc-aaaaaaaa"]) {
    const st = await statusOf(keys, await handle(post("activate", { licence, install_id: pc }), s, keys, cfg));
    assert(st.st === "active" && st.iid === pc, `${pc} ${st.st}`);
  }
  const fourth = await statusOf(keys, await handle(post("activate", { licence, install_id: "pc-dddddddd" }), s, keys, cfg));
  assert(fourth.st === "limit");
  await handle(post("deactivate", { licence, install_id: "pc-bbbbbbbb" }), s, keys, cfg);
  const retry = await statusOf(keys, await handle(post("check", { licence, install_id: "pc-dddddddd" }), s, keys, cfg));
  assert(retry.st === "active");
});

Deno.test("revoked licence answers revoked", async () => {
  const { keys } = await testKeys();
  const s = new MemoryStore();
  const lic = await issue(s, keys);
  s.licences.get(lic.id)!.revoked_at = new Date().toISOString();
  const st = await statusOf(keys, await handle(post("check", { licence: lic.licence, install_id: "pc-aaaaaaaa" }), s, keys, cfg));
  assert(st.st === "revoked");
});

Deno.test("tampered or foreign licences are rejected", async () => {
  const { keys } = await testKeys();
  const other = await testKeys();
  const s = new MemoryStore();
  const { licence } = await issue(s, keys);
  const forged = (await issue(new MemoryStore(), other.keys)).licence;
  assert((await handle(post("activate", { licence: forged, install_id: "pc-aaaaaaaa" }), s, keys, cfg)).status === 400);
  const lines = licence.split("\n");
  lines[1] = lines[1].slice(0, 5) + (lines[1][5] === "A" ? "B" : "A") + lines[1].slice(6);
  assert((await handle(post("activate", { licence: lines.join("\n"), install_id: "pc-aaaaaaaa" }), s, keys, cfg)).status === 400);
  assert((await handle(post("activate", { licence, install_id: "x" }), s, keys, cfg)).status === 400);
});

Deno.test("resend never reveals whether an email bought Pro, and is rate limited", async () => {
  const { keys } = await testKeys();
  const s = new MemoryStore();
  const mail = new MemoryMailer();
  await issue(s, keys);
  const a = await (await handle(post("resend", { email: "sam@example.com" }), s, keys, cfg, { mailer: mail })).json();
  const b = await (await handle(post("resend", { email: "nobody@example.com" }), s, keys, cfg, { mailer: mail })).json();
  assert(a.message === b.message && mail.sent.length === 1 && mail.sent[0].text.includes("BEGIN WIFIDROP LICENCE"));
  const codes = [];
  for (let i = 0; i < 3; i++) codes.push((await handle(post("resend", { email: "sam@example.com" }, {}, "9.9.9.9"), s, keys, cfg)).status);
  assert(codes.join() === "200,200,429", codes.join());
});

Deno.test("browsers from other sites are refused; the app (no Origin) is allowed", async () => {
  const { keys } = await testKeys();
  const s = new MemoryStore();
  const { licence } = await issue(s, keys);
  const evil = await handle(post("activate", { licence, install_id: "pc-aaaaaaaa" }, { origin: "https://evil.example" }), s, keys, cfg);
  assert(evil.status === 403);
  const app = await handle(post("activate", { licence, install_id: "pc-aaaaaaaa" }), s, keys, cfg);
  assert(app.status === 200);
});

Deno.test("prints a sample for the Python cross-check", async () => {
  // deno test --allow-write=... writes it when LICENCE_SAMPLE is set; otherwise just checks the format.
  const { keys, publicB64 } = await testKeys();
  const s = new MemoryStore();
  const { licence } = await issue(s, keys);
  const st = await (await handle(post("activate", { licence, install_id: "pc-aaaaaaaa" }), s, keys, cfg)).json();
  let out: string | undefined;
  try { out = Deno.env.get("LICENCE_SAMPLE"); } catch { /* run without --allow-env: skip writing the sample */ }
  if (out) await Deno.writeTextFile(out, JSON.stringify({ public_key: publicB64, licence, status: st.status }));
  assert(b64url(new Uint8Array([255, 254])) === "__4");
});
