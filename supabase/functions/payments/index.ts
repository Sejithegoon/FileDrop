// Supabase Edge Function: Paddle webhooks (purchases, refunds, chargebacks).
// POST /functions/v1/payments   called by Paddle, verified with PADDLE_WEBHOOK_SECRET
import { importKeys } from "../licence/logic.ts";
import { ResendMailer } from "../licence/store.ts";
import { type Config, handle } from "./logic.ts";
import { PaddleApi, SupabasePaymentStore } from "./store.ts";

const env = (k: string, d = "") => Deno.env.get(k) ?? d;
const sandbox = env("PADDLE_ENV", "sandbox") !== "production";

const config: Config = {
  webhookSecret: env("PADDLE_WEBHOOK_SECRET"),
  priceIds: env("PADDLE_PRICE_IDS").split(",").map((s) => s.trim()).filter(Boolean),
  sandbox,
  updatesMonths: Number(env("UPDATES_MONTHS", "12")),
  maxActivations: 3,
  toleranceSec: 300,
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
