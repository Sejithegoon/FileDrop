// Supabase Edge Function: Paddle webhooks (purchases, refunds, chargebacks).
// POST /functions/v1/payments   called by Paddle, verified with PADDLE_WEBHOOK_SECRET
import { importKeys } from "../licence/logic.ts";
import { ResendMailer } from "../licence/store.ts";
import { type Config, handle } from "./logic.ts";
import { PaddleApi, SupabasePaymentStore } from "./store.ts";

const env = (k: string, d = "") => Deno.env.get(k) ?? d;
const sandbox = env("PADDLE_ENV", "sandbox") !== "production";

// Paddle's webhook IPs, fetched from Paddle (never hard-coded) and cached for an hour.
let ipCache: { at: number; cidrs: string[] } | null = null;
async function paddleIps(): Promise<string[] | null> {
  if (ipCache && Date.now() - ipCache.at < 3600_000) return ipCache.cidrs;
  try {
    const r = await fetch(`${sandbox ? "https://sandbox-api.paddle.com" : "https://api.paddle.com"}/ips`);
    const cidrs = (await r.json())?.data?.ipv4_cidrs;
    if (!r.ok || !Array.isArray(cidrs) || !cidrs.length) throw new Error(`status ${r.status}`);
    ipCache = { at: Date.now(), cidrs };
    return cidrs;
  } catch (err) {
    console.error("Could not fetch Paddle IPs; relying on the signature check", err);
    return ipCache?.cidrs ?? null;
  }
}

const config: Config = {
  webhookSecret: env("PADDLE_WEBHOOK_SECRET"),
  priceIds: env("PADDLE_PRICE_IDS").split(",").map((s) => s.trim()).filter(Boolean),
  sandbox,
  updatesMonths: Number(env("UPDATES_MONTHS", "12")),
  maxActivations: 3,
  toleranceSec: 300,
  paddleIps,
  licence: {
    allowedOrigins: [], ipSalt: "", rateLimit: 0, resendLimit: 0, rateWindowMs: 0,
    defaultUpdatesMonths: Number(env("UPDATES_MONTHS", "12")),
    websiteUrl: env("WEBSITE_URL", "https://wifidrop.ca"),
  },
};

const keys = await importKeys(env("LICENCE_PRIVATE_KEY"), env("LICENCE_PUBLIC_KEY"));
const store = new SupabasePaymentStore(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"));
const paddle = new PaddleApi(env("PADDLE_API_KEY"), sandbox);
const mailer = env("RESEND_API_KEY") ? new ResendMailer(env("RESEND_API_KEY"), env("EMAIL_FROM", "WiFiDrop <onboarding@resend.dev>")) : null;

Deno.serve((req) => handle(req, store, keys, paddle, mailer, config));
