// Supabase Edge Function: WiFiDrop Pro licences.
// POST /functions/v1/licence/{activate|check|deactivate}   from the WiFiDrop app
// POST /functions/v1/licence/resend                         from the website
// POST /functions/v1/licence/issue                          from the inbox (admins only)
import { type Config, handle, importKeys } from "./logic.ts";
import { ResendMailer, SupabaseLicenceStore } from "./store.ts";

const env = (k: string, d = "") => Deno.env.get(k) ?? d;

const config: Config = {
  allowedOrigins: env("ALLOWED_ORIGINS", "https://wifidrop.ca,https://www.wifidrop.ca").split(",").map((s) => s.trim()).filter(Boolean),
  ipSalt: env("IP_SALT") || crypto.randomUUID(),
  rateLimit: Number(env("LICENCE_RATE_LIMIT", "30")),
  resendLimit: 3,
  rateWindowMs: 10 * 60 * 1000,
  defaultUpdatesMonths: Number(env("UPDATES_MONTHS", "12")),
  websiteUrl: env("WEBSITE_URL", "https://wifidrop.ca"),
};

const keys = await importKeys(env("LICENCE_PRIVATE_KEY"), env("LICENCE_PUBLIC_KEY"));
const store = new SupabaseLicenceStore(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"));
const mailer = env("RESEND_API_KEY") ? new ResendMailer(env("RESEND_API_KEY"), env("EMAIL_FROM", "WiFiDrop <onboarding@resend.dev>")) : null;

Deno.serve((req) => handle(req, store, keys, config, { mailer }));
