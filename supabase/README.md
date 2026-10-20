# WiFiDrop backend on Supabase

One Supabase project (Canada Central) runs everything the website and the app talk to:

| Edge Function | Used by | Does |
| --- | --- | --- |
| `forms` | the website | Feedback, contact, beta sign-ups, Pro waitlist, unsubscribe |
| `licence` | the app, the website, the inbox | Activates, checks and frees Pro licences; re-sends licences; lets admins issue and email them |
| `payments` | Paddle | Purchase → issue and email a licence; full refund or chargeback → revoke it. Only accepts Paddle's IP addresses and signature |

Admins read everything at https://wifidrop.ca/admin.html (Supabase sign-in; only accounts in `public.admins`).

## Database

Apply the migrations in order in **SQL Editor** (each is safe to run again):
`migrations/20261016000000_forms.sql`, `migrations/20261017000000_licences.sql`, `migrations/20261018000000_payments.sql`.

Make an inbox admin (after creating the user under **Authentication → Users**, with sign-ups turned off):
```sql
insert into public.admins (user_id) select id from auth.users where email = 'you@example.com';
```

## Deploy

```
npx supabase@latest login
npx supabase@latest functions deploy forms --project-ref <ref> --no-verify-jwt --use-api
npx supabase@latest functions deploy licence --project-ref <ref> --no-verify-jwt --use-api
npx supabase@latest functions deploy payments --project-ref <ref> --no-verify-jwt --use-api
```

## Secrets

Set with `npx supabase@latest secrets set --project-ref <ref> NAME=value` (type secret values in your own terminal, never in chat or in the repo).

| Name | What |
| --- | --- |
| `ALLOWED_ORIGINS` | `https://wifidrop.ca,https://www.wifidrop.ca` |
| `WEBSITE_URL` | `https://wifidrop.ca` (links in licence emails) |
| `IP_SALT` | Any long random string; keeps hashed IPs for rate limits stable |
| `LICENCE_PRIVATE_KEY`, `LICENCE_PUBLIC_KEY` | Ed25519 signing keys. The private key exists only here and in your password manager; the public key is built into the app (`app/core/edition.py`) |
| `RESEND_API_KEY`, `EMAIL_FROM` | Email sending; `EMAIL_FROM` is `WiFiDrop <licences@wifidrop.ca>` |
| `PADDLE_ENV` | `production` (or `sandbox` for testing) |
| `PADDLE_PRICE_IDS` | The live `pri_…` of WiFiDrop Pro |
| `PADDLE_WEBHOOK_SECRET`, `PADDLE_API_KEY` | From the live Paddle notification destination and API key (Customers: read) |

Optional: `TURNSTILE_SECRET`, `RATE_LIMIT` (5 per 10 min), `MAX_ATTACHMENT_MB` (5), `RETENTION_DAYS` (730), `UPDATES_MONTHS` (12).

Never put the secret or `service_role` key in the site; functions get it from Supabase automatically.
The site only uses the project URL and the publishable key (`site/assets/js/config.js`).

## Tests

```
deno test supabase/functions
```
