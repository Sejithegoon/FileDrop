# Website forms on Supabase

The feedback, contact, beta and waitlist forms post to the `forms` Edge Function, which stores them in Postgres (Canada Central).
You read them at `admin.html` on the website.

## One-time setup

1. Apply the database tables. Open the dashboard, go to **SQL Editor**, paste `migrations/20261016000000_forms.sql`, and click **Run**.
   It is safe to run again.
2. Deploy the function from the repo folder. The sign-in opens your browser.
   ```
   npx supabase@latest login
   npx supabase@latest functions deploy forms --project-ref <ref> --no-verify-jwt
   ```
3. Set the function secrets. `IP_SALT` is any long random string, and keeps the hashed IPs used for rate limiting stable.
   ```
   npx supabase@latest secrets set --project-ref <ref> IP_SALT=<random> ALLOWED_ORIGINS=https://sejithegoon.github.io
   ```
   - Optional: `TURNSTILE_SECRET`, `RATE_LIMIT` (default 5 per 10 min), `MAX_ATTACHMENT_MB` (5) and `RETENTION_DAYS` (730).
   - When the domain is live, add it to `ALLOWED_ORIGINS`, separated by commas.
4. Create your inbox account:
   - Go to **Authentication → Users → Add user** and use "Create new user" with your email and a strong password.
   - Turn sign-ups off under **Authentication → Sign In / Providers → Allow new users to sign up**.
   - In the SQL Editor, make the account an admin:
     ```sql
     insert into public.admins (user_id) select id from auth.users where email = 'you@example.com';
     ```
5. In `site/assets/js/config.js`, set:
   - `apiBase` to `https://<ref>.supabase.co/functions/v1/forms`
   - `supabaseUrl` to `https://<ref>.supabase.co`
   - `supabaseKey` to the **publishable** key

   Then publish with `build/publish-site.ps1`.

Never put the secret or `service_role` key in the site. The function gets it from Supabase automatically.

## Tests

```
deno test supabase/functions/forms
```
