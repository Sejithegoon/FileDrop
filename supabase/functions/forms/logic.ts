// WiFiDrop website forms: request handling, validation and spam protection.
// Storage is behind the Store interface so this file can be tested without Supabase.

export interface Submission {
  kind: "feedback" | "contact" | "beta";
  category: string;
  name: string;
  email: string;
  subject: string;
  message: string;
  details: Record<string, unknown>;
  ip_hash: string;
}

export interface Store {
  countHits(key: string, sinceMs: number): Promise<number>;
  addHit(key: string): Promise<void>;
  insertSubmission(s: Submission): Promise<number>;
  saveAttachment(submissionId: number, filename: string, contentType: string, data: Uint8Array): Promise<void>;
  upsertWaitlist(email: string, consentText: string, ipHash: string, token: string): Promise<void>;
  unsubscribe(token: string): Promise<boolean>;
  purgeOlderThan(days: number): Promise<void>;
}

export interface Config {
  allowedOrigins: string[];
  ipSalt: string;
  turnstileSecret: string;
  maxAttachmentBytes: number;
  rateLimit: number;
  rateWindowMs: number;
  minFillMs: number;
  retentionDays: number;
  purgeChance: number;
}

export const WAITLIST_CONSENT = "Yes, email me about the WiFiDrop Pro launch. I can unsubscribe at any time.";
const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$/;
const ATTACH_TYPES: Record<string, string> = {
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
  ".gif": "image/gif", ".txt": "text/plain", ".log": "text/plain",
};
const MAX = { name: 100, email: 254, subject: 200, message: 5000, short: 200 };

class FormError extends Error {
  constructor(message: string, public status = 400, public code = "INVALID") {
    super(message);
  }
}

function text(form: FormData, key: string, max: number, label: string, required = false): string {
  const raw = form.get(key);
  // Browsers send line breaks in form fields as \r\n; store plain \n.
  const value = (typeof raw === "string" ? raw : "").replaceAll("\u0000", "").replaceAll("\r\n", "\n").trim();
  if (required && !value) throw new FormError(`${label} is required.`);
  if (value.length > max) throw new FormError(`${label} is too long (maximum ${max} characters).`);
  return value;
}

function email(form: FormData, required: boolean): string {
  const value = text(form, "email", MAX.email, "Email", required);
  if (value && !EMAIL_RE.test(value)) throw new FormError("Please enter a valid email address.");
  return value.toLowerCase();
}

function choice(value: string, allowed: string[], label: string): string {
  if (!allowed.includes(value)) throw new FormError(`Please choose a ${label}.`);
  return value;
}

async function sha256(input: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function randomToken(bytes = 24): string {
  const a = crypto.getRandomValues(new Uint8Array(bytes));
  return btoa(String.fromCharCode(...a)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function corsHeaders(origin: string | null, cfg: Config): Record<string, string> {
  const h: Record<string, string> = {
    "Vary": "Origin",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  };
  if (origin && cfg.allowedOrigins.includes(origin)) {
    h["Access-Control-Allow-Origin"] = origin;
    h["Access-Control-Allow-Methods"] = "POST, OPTIONS";
    h["Access-Control-Allow-Headers"] = "content-type";
    h["Access-Control-Max-Age"] = "86400";
  }
  return h;
}

function json(body: unknown, status: number, headers: Record<string, string>): Response {
  return new Response(JSON.stringify(body), { status, headers: { ...headers, "Content-Type": "application/json" } });
}

export function clientIp(req: Request): string {
  const fwd = req.headers.get("x-forwarded-for") || "";
  return fwd.split(",")[0].trim() || req.headers.get("x-real-ip") || "";
}

async function verifyTurnstile(secret: string, token: string, ip: string, fetcher: typeof fetch): Promise<boolean> {
  if (!token) return false;
  try {
    const r = await fetcher("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      body: new URLSearchParams({ secret, response: token, remoteip: ip }),
    });
    return Boolean((await r.json()).success);
  } catch {
    return false;
  }
}

/** Spam checks shared by every form. Returns the salted IP hash. */
async function guard(req: Request, form: FormData, name: string, store: Store, cfg: Config,
  fetcher: typeof fetch, now: number): Promise<string> {
  if (text(form, "website", 500, "Website")) throw new FormError("Submission rejected.", 400, "SPAM");
  const started = Number(text(form, "started", 20, "Started"));
  if (started && now - started < cfg.minFillMs) {
    throw new FormError("That was quick! Please take a moment and send the form again.", 400, "TOO_FAST");
  }
  const ip = clientIp(req);
  const ipHash = (await sha256(cfg.ipSalt + ip)).slice(0, 16);
  const key = `${name}:${ipHash}`;
  if (await store.countHits(key, now - cfg.rateWindowMs) >= cfg.rateLimit) {
    throw new FormError("Too many submissions from your network. Please try again in a few minutes.", 429, "RATE_LIMITED");
  }
  await store.addHit(key);
  if (cfg.turnstileSecret && !(await verifyTurnstile(cfg.turnstileSecret, text(form, "turnstile", 4000, "Check"), ip, fetcher))) {
    throw new FormError("Please complete the check that you're human.", 400, "CAPTCHA");
  }
  return ipHash;
}

async function feedback(form: FormData, ipHash: string, store: Store, cfg: Config) {
  const category = choice(text(form, "category", 20, "Type"), ["bug", "idea", "question"], "type of feedback");
  const message = text(form, "message", MAX.message, "Your message", true);
  const details = {
    steps: text(form, "steps", MAX.message, "Steps"),
    app_version: text(form, "app_version", MAX.short, "Version"),
    windows: text(form, "windows", MAX.short, "Windows version"),
    device: text(form, "device", MAX.short, "Phone or browser"),
  };
  let file: { name: string; type: string; data: Uint8Array } | null = null;
  const upload = form.get("attachment");
  if (upload instanceof File && upload.name && upload.size > 0) {
    const ext = (upload.name.match(/\.[^.]+$/)?.[0] || "").toLowerCase();
    if (!ATTACH_TYPES[ext]) throw new FormError("Attach a screenshot (PNG, JPG, WebP, GIF) or a log file (TXT, LOG).");
    if (upload.size > cfg.maxAttachmentBytes) {
      throw new FormError(`The attachment is larger than ${Math.round(cfg.maxAttachmentBytes / 1048576)} MB.`, 413, "TOO_LARGE");
    }
    const safe = upload.name.replace(/[^\w.\- ]/g, "_").slice(0, 120) || `attachment${ext}`;
    file = { name: safe, type: ATTACH_TYPES[ext], data: new Uint8Array(await upload.arrayBuffer()) };
  }
  const id = await store.insertSubmission({
    kind: "feedback", category, name: "", email: email(form, false), subject: message.split("\n")[0].slice(0, 120),
    message, details, ip_hash: ipHash,
  });
  if (file) await store.saveAttachment(id, file.name, file.type, file.data);
  return { ok: true, id, message: "Thanks! Your feedback has been received." };
}

async function contact(form: FormData, ipHash: string, store: Store) {
  const topic = choice(text(form, "topic", 20, "Topic"), ["general", "partnership", "press", "privacy"], "topic");
  const id = await store.insertSubmission({
    kind: "contact", category: topic, name: text(form, "name", MAX.name, "Your name", true), email: email(form, true),
    subject: text(form, "subject", MAX.subject, "Subject"), message: text(form, "message", MAX.message, "Your message", true),
    details: {}, ip_hash: ipHash,
  });
  return { ok: true, id, message: "Thanks! We'll reply by email, usually within two business days." };
}

async function beta(form: FormData, ipHash: string, store: Store, now: number) {
  if (text(form, "consent", 10, "Consent") !== "yes") throw new FormError("Please agree to be contacted about the beta.");
  const allowed = ["iphone", "android", "windows", "mac", "other"];
  const phones = form.getAll("phones").filter((p): p is string => typeof p === "string" && allowed.includes(p)).slice(0, 5);
  const id = await store.insertSubmission({
    kind: "beta", category: "signup", name: text(form, "name", MAX.name, "Your name", true), email: email(form, true),
    subject: "", message: text(form, "use_case", MAX.message, "Use case"),
    details: { windows: text(form, "windows", MAX.short, "Windows version"), phones, consent_at: new Date(now).toISOString() },
    ip_hash: ipHash,
  });
  return { ok: true, id, message: "You're on the list! We'll email you when the next beta build is ready." };
}

async function waitlist(form: FormData, ipHash: string, store: Store) {
  if (text(form, "consent", 10, "Consent") !== "yes") throw new FormError("Please tick the box to agree to the launch email.");
  await store.upsertWaitlist(email(form, true), WAITLIST_CONSENT, ipHash, randomToken());
  return { ok: true, message: "You're on the list. We'll send one email when Pro launches." };
}

export async function handle(req: Request, store: Store, cfg: Config,
  opts: { fetcher?: typeof fetch; now?: number; random?: () => number } = {}): Promise<Response> {
  const origin = req.headers.get("origin");
  const headers = corsHeaders(origin, cfg);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers });
  if (req.method !== "POST") return json({ ok: false, code: "METHOD", message: "Use POST." }, 405, headers);
  if (origin && !cfg.allowedOrigins.includes(origin)) {
    return json({ ok: false, code: "ORIGIN", message: "Request blocked." }, 403, headers);
  }
  const route = new URL(req.url).pathname.replace(/\/+$/, "").split("/").pop() || "";
  const now = opts.now ?? Date.now();
  try {
    if ((opts.random ?? Math.random)() < cfg.purgeChance) await store.purgeOlderThan(cfg.retentionDays);
    let form: FormData;
    try {
      form = await req.formData();
    } catch {
      throw new FormError("The form could not be read.");
    }
    if (route === "unsubscribe") {
      const ok = await store.unsubscribe(text(form, "token", 200, "Token", true));
      return json({ ok, message: ok ? "You've been unsubscribed. We won't email you again." : "This link has already been used or isn't valid." }, 200, headers);
    }
    if (!["feedback", "contact", "beta", "waitlist"].includes(route)) {
      return json({ ok: false, code: "NOT_FOUND", message: "Unknown form." }, 404, headers);
    }
    const ipHash = await guard(req, form, route, store, cfg, opts.fetcher ?? fetch, now);
    const body = route === "feedback" ? await feedback(form, ipHash, store, cfg)
      : route === "contact" ? await contact(form, ipHash, store)
      : route === "beta" ? await beta(form, ipHash, store, now)
      : await waitlist(form, ipHash, store);
    return json(body, 200, headers);
  } catch (err) {
    if (err instanceof FormError) return json({ ok: false, code: err.code, message: err.message }, err.status, headers);
    console.error("forms error", err);
    return json({ ok: false, code: "SERVER", message: "Something went wrong on our side. Please try again." }, 500, headers);
  }
}
