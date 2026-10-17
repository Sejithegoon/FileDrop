// Supabase Edge Function: FileDrop website forms.
// POST /functions/v1/forms/{feedback|contact|beta|waitlist|unsubscribe}
import { type Config, handle } from "./logic.ts";
import { SupabaseStore } from "./store.ts";

const env = (k: string, d = "") => Deno.env.get(k) ?? d;

const config: Config = {
  allowedOrigins: env("ALLOWED_ORIGINS", "https://sejithegoon.github.io").split(",").map((s) => s.trim()).filter(Boolean),
  ipSalt: env("IP_SALT") || crypto.randomUUID(), // set IP_SALT so hashes stay stable between restarts
  turnstileSecret: env("TURNSTILE_SECRET"),
  maxAttachmentBytes: Number(env("MAX_ATTACHMENT_MB", "5")) * 1048576,
  rateLimit: Number(env("RATE_LIMIT", "5")),
  rateWindowMs: 10 * 60 * 1000,
  minFillMs: 2000,
  retentionDays: Number(env("RETENTION_DAYS", "730")),
  purgeChance: 0.02,
};

const store = new SupabaseStore(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"));

Deno.serve((req) => handle(req, store, config));
