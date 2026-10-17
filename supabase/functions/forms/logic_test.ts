// Run: deno test supabase/functions/forms
import { type Config, handle, type Store, type Submission } from "./logic.ts";

class MemoryStore implements Store {
  hits: { key: string; at: number }[] = [];
  subs: (Submission & { id: number; created: number })[] = [];
  files: { submissionId: number; filename: string; type: string; size: number }[] = [];
  wait = new Map<string, { token: string; unsub: boolean; consent: string }>();
  purged = 0;
  countHits(key: string, since: number) { return Promise.resolve(this.hits.filter((h) => h.key === key && h.at > since).length); }
  addHit(key: string) { this.hits.push({ key, at: Date.now() }); return Promise.resolve(); }
  insertSubmission(s: Submission) { const id = this.subs.length + 1; this.subs.push({ ...s, id, created: Date.now() }); return Promise.resolve(id); }
  saveAttachment(submissionId: number, filename: string, type: string, data: Uint8Array) {
    this.files.push({ submissionId, filename, type, size: data.length }); return Promise.resolve();
  }
  upsertWaitlist(email: string, consent: string, _ip: string, token: string) { this.wait.set(email, { token, unsub: false, consent }); return Promise.resolve(); }
  unsubscribe(token: string) {
    for (const v of this.wait.values()) if (v.token === token && !v.unsub) { v.unsub = true; return Promise.resolve(true); }
    return Promise.resolve(false);
  }
  purgeOlderThan() { this.purged++; return Promise.resolve(); }
}

const cfg: Config = {
  allowedOrigins: ["https://sejithegoon.github.io"], ipSalt: "salt", turnstileSecret: "", maxAttachmentBytes: 1024 * 1024,
  rateLimit: 5, rateWindowMs: 600000, minFillMs: 2000, retentionDays: 730, purgeChance: 0,
};
const ORIGIN = "https://sejithegoon.github.io";

function assert(cond: unknown, msg = "assertion failed"): asserts cond { if (!cond) throw new Error(msg); }

function post(route: string, fields: Record<string, string | string[] | File>, origin: string | null = ORIGIN, ip = "1.2.3.4") {
  const fd = new FormData();
  fd.set("started", String(Date.now() - 10000));
  for (const [k, v] of Object.entries(fields)) {
    if (Array.isArray(v)) v.forEach((x) => fd.append(k, x)); else fd.set(k, v);
  }
  const headers: Record<string, string> = { "x-forwarded-for": `${ip}, 10.0.0.1` };
  if (origin) headers.origin = origin;
  return new Request(`https://x.supabase.co/functions/v1/forms/${route}`, { method: "POST", body: fd, headers });
}

Deno.test("bug report with screenshot", async () => {
  const s = new MemoryStore();
  const r = await handle(post("feedback", {
    category: "bug", message: "Upload stops at 99%\nOn iPhone", app_version: "0.1.0", device: "iPhone Safari",
    email: "Sam@Example.com", attachment: new File([new Uint8Array([137, 80, 78, 71])], "shot.png", { type: "image/png" }),
  }), s, cfg);
  assert(r.status === 200, `status ${r.status}`);
  assert(r.headers.get("access-control-allow-origin") === ORIGIN, "CORS header");
  assert(s.subs[0].email === "sam@example.com" && s.subs[0].subject === "Upload stops at 99%");
  assert(s.files.length === 1 && s.files[0].type === "image/png");
});

Deno.test("attachment rules", async () => {
  const s = new MemoryStore();
  const exe = await handle(post("feedback", { category: "bug", message: "x", attachment: new File(["MZ"], "evil.exe") }), s, cfg);
  assert(exe.status === 400);
  const big = await handle(post("feedback", { category: "bug", message: "x", attachment: new File([new Uint8Array(1024 * 1024 + 5)], "big.png") }), s, cfg);
  assert(big.status === 413);
  assert(s.subs.length === 0, "nothing stored for rejected uploads");
});

Deno.test("spam guards", async () => {
  const s = new MemoryStore();
  const base = { topic: "general", name: "A", email: "a@x.io", message: "hi" };
  assert((await (await handle(post("contact", { ...base, website: "http://spam" }), s, cfg)).json()).code === "SPAM");
  const fd = post("contact", { ...base, started: String(Date.now()) });
  assert((await (await handle(fd, s, cfg)).json()).code === "TOO_FAST");
  const codes = [];
  for (let i = 0; i < 6; i++) codes.push((await handle(post("contact", base, ORIGIN, "9.9.9.9"), s, cfg)).status);
  assert(codes.join() === "200,200,200,200,200,429", codes.join());
  assert((await handle(post("contact", base, "https://evil.example"), s, cfg)).status === 403);
});

Deno.test("preflight and methods", async () => {
  const s = new MemoryStore();
  const pre = await handle(new Request("https://x/functions/v1/forms/contact", { method: "OPTIONS", headers: { origin: ORIGIN } }), s, cfg);
  assert(pre.status === 204 && pre.headers.get("access-control-allow-methods")?.includes("POST"));
  const bad = await handle(new Request("https://x/functions/v1/forms/contact", { method: "OPTIONS", headers: { origin: "https://evil.example" } }), s, cfg);
  assert(!bad.headers.get("access-control-allow-origin"), "no CORS for other sites");
  assert((await handle(new Request("https://x/functions/v1/forms/contact"), s, cfg)).status === 405);
  assert((await handle(post("nope", {}), s, cfg)).status === 404);
});

Deno.test("validation", async () => {
  const s = new MemoryStore();
  const r = await handle(post("contact", { topic: "general", name: "A", email: "not-an-email", message: "hi" }), s, cfg);
  assert(r.status === 400 && (await r.json()).message.includes("valid email"));
  assert((await handle(post("feedback", { category: "rant", message: "x" }), s, cfg)).status === 400);
});

Deno.test("beta needs consent and filters devices", async () => {
  const s = new MemoryStore();
  const data = { name: "Mia", email: "mia@example.com", phones: ["iphone", "android", "toaster"], use_case: "Class" };
  assert((await handle(post("beta", data), s, cfg)).status === 400);
  assert((await handle(post("beta", { ...data, consent: "yes" }), s, cfg)).status === 200);
  assert(JSON.stringify(s.subs[0].details.phones) === '["iphone","android"]' && s.subs[0].details.consent_at);
});

Deno.test("waitlist consent and unsubscribe", async () => {
  const s = new MemoryStore();
  assert((await handle(post("waitlist", { email: "a@b.co" }), s, cfg)).status === 400);
  assert((await handle(post("waitlist", { email: "A@B.co", consent: "yes" }), s, cfg)).status === 200);
  const entry = s.wait.get("a@b.co")!;
  assert(entry.consent.includes("unsubscribe"));
  const first = await (await handle(post("unsubscribe", { token: entry.token }), s, cfg)).json();
  const again = await (await handle(post("unsubscribe", { token: entry.token }), s, cfg)).json();
  assert(first.ok === true && again.ok === false);
});

Deno.test("purge runs occasionally", async () => {
  const s = new MemoryStore();
  await handle(post("contact", { topic: "general", name: "A", email: "a@x.io", message: "hi" }), s, { ...cfg, purgeChance: 1 });
  assert(s.purged === 1);
});

Deno.test("store failures become a friendly 500", async () => {
  const s = new MemoryStore();
  s.insertSubmission = () => Promise.reject(new Error("db down"));
  const r = await handle(post("contact", { topic: "general", name: "A", email: "a@x.io", message: "hi" }), s, cfg);
  assert(r.status === 500 && (await r.json()).code === "SERVER");
});
