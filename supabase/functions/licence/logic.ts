// FileDrop Pro licences: issue, activate on up to N PCs, check, deactivate, re-send.
// Licences and statuses are JSON signed with Ed25519. The private key exists only in this
// function's secrets; the FileDrop app has the public key and verifies everything offline.

export interface LicenceRow {
  id: string;
  email: string;
  updates_until: string;
  max_activations: number;
  revoked_at: string | null;
  licence_text: string;
}

export interface LicenceStore {
  countHits(key: string, sinceMs: number): Promise<number>;
  addHit(key: string): Promise<void>;
  getLicence(id: string): Promise<LicenceRow | null>;
  licencesByEmail(email: string): Promise<LicenceRow[]>;
  insertLicence(row: LicenceRow & { note: string; order_id: string | null }): Promise<void>;
  activations(licenceId: string): Promise<string[]>; // install IDs
  addActivation(licenceId: string, installId: string, appVersion: string): Promise<void>;
  touchActivation(licenceId: string, installId: string, appVersion: string): Promise<void>;
  removeActivation(licenceId: string, installId: string): Promise<void>;
  isAdmin(authorization: string): Promise<boolean>;
}

export interface Mailer {
  send(to: string, subject: string, text: string): Promise<void>;
}

export interface Config {
  allowedOrigins: string[];
  ipSalt: string;
  rateLimit: number; // per IP per window, app routes
  resendLimit: number; // per IP and per email per hour
  rateWindowMs: number;
  defaultUpdatesMonths: number;
  websiteUrl: string;
}

export interface Keys {
  sign(data: Uint8Array): Promise<Uint8Array>;
  verify(sig: Uint8Array, data: Uint8Array): Promise<boolean>;
}

const BEGIN = "-----BEGIN FILEDROP LICENCE-----";
const END = "-----END FILEDROP LICENCE-----";
const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$/;
const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"; // Crockford base32: no I, L, O, U
const INSTALL_RE = /^[A-Za-z0-9_-]{8,64}$/;

class HttpError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export async function importKeys(privatePkcs8B64: string, publicRawB64: string): Promise<Keys> {
  const raw = (b64: string) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const priv = privatePkcs8B64
    ? await crypto.subtle.importKey("pkcs8", raw(privatePkcs8B64), { name: "Ed25519" }, false, ["sign"])
    : null;
  const pub = await crypto.subtle.importKey("raw", raw(publicRawB64), { name: "Ed25519" }, false, ["verify"]);
  return {
    async sign(data) {
      if (!priv) throw new Error("LICENCE_PRIVATE_KEY is not set");
      return new Uint8Array(await crypto.subtle.sign("Ed25519", priv, data.slice()));
    },
    async verify(sig, data) {
      return await crypto.subtle.verify("Ed25519", pub, sig.slice(), data.slice());
    },
  };
}

export const b64url = (b: Uint8Array) =>
  btoa(String.fromCharCode(...b)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
const unb64url = (s: string) => Uint8Array.from(atob(s.replaceAll("-", "+").replaceAll("_", "/")), (c) => c.charCodeAt(0));

export async function signJson(keys: Keys, payload: Record<string, unknown>): Promise<string> {
  const data = new TextEncoder().encode(JSON.stringify(payload));
  return `${b64url(data)}.${b64url(await keys.sign(data))}`;
}

export function formatLicence(blob: string): string {
  const lines = blob.match(/.{1,64}/g) || [];
  return [BEGIN, ...lines, END].join("\n");
}

/** Verifies a pasted licence and returns its payload, or null. */
export async function readLicence(keys: Keys, text: string): Promise<Record<string, unknown> | null> {
  let body = String(text || "");
  if (body.includes(BEGIN) && body.includes(END)) body = body.split(BEGIN)[1].split(END)[0];
  body = body.replace(/\s+/g, "");
  const parts = body.split(".");
  if (parts.length !== 2) return null;
  try {
    const data = unb64url(parts[0]);
    if (!(await keys.verify(unb64url(parts[1]), data))) return null;
    const payload = JSON.parse(new TextDecoder().decode(data));
    return payload?.typ === "licence" && payload?.v === 1 && typeof payload.lid === "string" ? payload : null;
  } catch {
    return null;
  }
}

export function newLicenceId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  const chars = [...bytes].map((b) => ALPHABET[b % 32]).join("");
  return `FDP-${chars.slice(0, 4)}-${chars.slice(4, 8)}-${chars.slice(8, 12)}-${chars.slice(12, 16)}`;
}

async function sha256(input: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function addMonths(date: Date, months: number): string {
  const d = new Date(date);
  d.setUTCMonth(d.getUTCMonth() + months);
  return d.toISOString().slice(0, 10);
}

function licenceEmail(cfg: Config, rows: LicenceRow[]): string {
  const blocks = rows.map((r) => `Licence ${r.id} (updates until ${r.updates_until}):\n\n${r.licence_text}`).join("\n\n");
  return `Thank you for buying FileDrop Pro!

To turn on Pro, open the FileDrop window on your PC, go to Licence, paste the whole licence below
(including the BEGIN and END lines) and press Activate Pro.

${blocks}

You can use a licence on up to 3 PCs. To move it to a new PC, choose "Remove from this PC" on the old one first.
Keep this email: you'll need the licence if you reinstall Windows.

Need help? ${cfg.websiteUrl}/contact.html
`;
}

export async function handle(req: Request, store: LicenceStore, keys: Keys, cfg: Config,
  opts: { mailer?: Mailer | null; now?: number } = {}): Promise<Response> {
  const origin = req.headers.get("origin");
  const headers: Record<string, string> = { "Vary": "Origin", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" };
  if (origin && cfg.allowedOrigins.includes(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Access-Control-Allow-Methods"] = "POST, OPTIONS";
    headers["Access-Control-Allow-Headers"] = "content-type, authorization, apikey, x-client-info";
    headers["Access-Control-Max-Age"] = "86400";
  }
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { ...headers, "Content-Type": "application/json" } });
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers });
  if (req.method !== "POST") return json({ ok: false, code: "METHOD", message: "Use POST." }, 405);
  // The FileDrop app sends no Origin header; browsers always do, so other websites are refused.
  if (origin && !cfg.allowedOrigins.includes(origin)) return json({ ok: false, code: "ORIGIN", message: "Request blocked." }, 403);

  const now = opts.now ?? Date.now();
  const route = new URL(req.url).pathname.replace(/\/+$/, "").split("/").pop() || "";
  const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  const ipHash = (await sha256(cfg.ipSalt + ip)).slice(0, 16);

  const limit = async (key: string, max: number, windowMs: number) => {
    if (await store.countHits(key, now - windowMs) >= max) {
      throw new HttpError(429, "RATE_LIMITED", "Too many requests. Please try again later.");
    }
    await store.addHit(key);
  };

  const status = (lid: string, iid: string, st: string) =>
    signJson(keys, { v: 1, typ: "status", lid, iid, st, at: new Date(now).toISOString() });

  try {
    let body: Record<string, unknown>;
    try {
      body = await req.json();
    } catch {
      throw new HttpError(400, "INVALID", "The request could not be read.");
    }
    const str = (k: string, max = 200) => String(body[k] ?? "").trim().slice(0, max);

    // ---- from the FileDrop app ----------------------------------------------------
    if (route === "activate" || route === "check" || route === "deactivate") {
      await limit(`licence:${ipHash}`, cfg.rateLimit, cfg.rateWindowMs);
      const lic = await readLicence(keys, String(body.licence ?? "").slice(0, 4000));
      if (!lic) throw new HttpError(400, "INVALID_LICENCE", "This licence isn't valid.");
      const iid = str("install_id", 64);
      if (!INSTALL_RE.test(iid)) throw new HttpError(400, "INVALID", "Missing install ID.");
      const lid = String(lic.lid);
      const row = await store.getLicence(lid);
      if (!row) throw new HttpError(404, "UNKNOWN_LICENCE", "This licence isn't in our records. Contact support.");
      const version = str("app_version", 20);
      if (route === "deactivate") {
        await store.removeActivation(lid, iid);
        return json({ ok: true, status: await status(lid, iid, "inactive"), message: "This PC was removed from your licence." });
      }
      if (row.revoked_at) {
        return json({ ok: true, status: await status(lid, iid, "revoked"), message: "This licence was cancelled." });
      }
      const active = await store.activations(lid);
      if (active.includes(iid)) {
        await store.touchActivation(lid, iid, version);
      } else if (active.length >= row.max_activations) {
        return json({ ok: true, status: await status(lid, iid, "limit"),
          message: `This licence is already active on ${row.max_activations} PCs.` });
      } else {
        await store.addActivation(lid, iid, version);
      }
      return json({ ok: true, status: await status(lid, iid, "active"), message: "FileDrop Pro is active on this PC." });
    }

    // ---- from the website: re-send a lost licence -----------------------------------
    if (route === "resend") {
      const email = str("email", 254).toLowerCase();
      if (!EMAIL_RE.test(email)) throw new HttpError(400, "INVALID", "Please enter a valid email address.");
      await limit(`resend-ip:${ipHash}`, cfg.resendLimit, 3600000);
      await limit(`resend-email:${(await sha256(cfg.ipSalt + email)).slice(0, 16)}`, cfg.resendLimit, 3600000);
      const rows = (await store.licencesByEmail(email)).filter((r) => !r.revoked_at);
      if (rows.length && opts.mailer) await opts.mailer.send(email, "Your FileDrop Pro licence", licenceEmail(cfg, rows));
      // Same answer either way, so nobody can find out who bought FileDrop.
      return json({ ok: true, message: "If that email address bought FileDrop Pro, we've sent the licence to it. Check your spam folder too." });
    }

    // ---- admins (the website inbox) ---------------------------------------------------
    if (route === "issue") {
      if (!(await store.isAdmin(req.headers.get("authorization") || ""))) {
        throw new HttpError(401, "NOT_ADMIN", "Sign in to the inbox as an admin.");
      }
      const email = str("email", 254).toLowerCase();
      if (!EMAIL_RE.test(email)) throw new HttpError(400, "INVALID", "Enter the customer's email address.");
      const updates = str("updates_until", 10) || addMonths(new Date(now), cfg.defaultUpdatesMonths);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(updates)) throw new HttpError(400, "INVALID", "Updates until must be a date.");
      const max = Number(body.max_activations ?? 3);
      if (!Number.isInteger(max) || max < 1 || max > 50) throw new HttpError(400, "INVALID", "PCs must be 1 to 50.");
      const id = newLicenceId();
      const text = formatLicence(await signJson(keys, {
        v: 1, typ: "licence", lid: id, ed: "pro", to: email, iat: new Date(now).toISOString(), upd: updates, max,
      }));
      await store.insertLicence({ id, email, updates_until: updates, max_activations: max, revoked_at: null,
        licence_text: text, note: str("note", 500), order_id: str("order_id", 100) || null });
      let emailed = false;
      if (body.send_email && opts.mailer) {
        await opts.mailer.send(email, "Your FileDrop Pro licence",
          licenceEmail(cfg, [{ id, email, updates_until: updates, max_activations: max, revoked_at: null, licence_text: text }]));
        emailed = true;
      }
      return json({ ok: true, id, licence: text, emailed });
    }

    return json({ ok: false, code: "NOT_FOUND", message: "Unknown request." }, 404);
  } catch (err) {
    if (err instanceof HttpError) return json({ ok: false, code: err.code, message: err.message }, err.status);
    console.error("licence error", err);
    return json({ ok: false, code: "SERVER", message: "Something went wrong on our side. Please try again." }, 500);
  }
}
