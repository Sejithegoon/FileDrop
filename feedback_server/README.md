# FileDrop feedback server

A small, self-hosted service for the website's forms: **feedback** (bug reports with optional screenshot or log, feature ideas, questions), **contact**, **beta sign-ups** and the **Pro waitlist**. It includes a private admin inbox. Everything is stored in one SQLite file on your own server, so form data stays in Canada.

## Run it locally

```bash
FEEDBACK_ADMIN_PASSWORD=choose-a-long-password .venv/Scripts/python -m feedback_server --site site --port 8095
```

- Website with working forms: http://127.0.0.1:8095
- Admin inbox: http://127.0.0.1:8095/admin

## Settings (environment variables)

| Variable | Default | What it does |
| --- | --- | --- |
| `FEEDBACK_ADMIN_PASSWORD` | (none) | Password for `/admin`. Required. Use 16+ characters. |
| `FEEDBACK_DATA_DIR` | `feedback-data` | Where the database and attachments are stored |
| `FEEDBACK_PUBLIC_URL` | (none) | Your site, e.g. `https://example.ca` (used in unsubscribe links) |
| `FEEDBACK_TRUST_PROXY` | `0` | Set to `1` behind nginx so the real visitor IP is used for rate limits |
| `FEEDBACK_SITE_DIR` | (none) | Also serve the static website (same as `--site`) |
| `FEEDBACK_MAX_ATTACHMENT_MB` | `5` | Largest screenshot or log accepted |
| `FEEDBACK_RETENTION_DAYS` | `730` | Submissions older than this are deleted automatically |
| `FEEDBACK_TURNSTILE_SECRET` | (none) | Optional Cloudflare Turnstile check (see below) |
| `FEEDBACK_SMTP_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `FEEDBACK_NOTIFY_TO`, `FEEDBACK_NOTIFY_FROM` | (none) | Optional: email you when something new arrives |
| `FEEDBACK_IP_SALT` | random per start | Set a fixed random value so rate-limit hashes survive restarts |

## Deploy on a Linux server (Canada)

1. Copy the repo (or just `feedback_server/` and `site/`) to `/opt/filedrop`, then create a virtual environment: `python3 -m venv .venv && .venv/bin/pip install fastapi uvicorn python-multipart`.
2. Create `/etc/filedrop-feedback.env` (readable only by root):
   ```ini
   FEEDBACK_ADMIN_PASSWORD=...long random password...
   FEEDBACK_DATA_DIR=/var/lib/filedrop-feedback
   FEEDBACK_PUBLIC_URL=https://example.ca
   FEEDBACK_TRUST_PROXY=1
   FEEDBACK_IP_SALT=...random 32 characters...
   ```
3. Create a systemd service, `/etc/systemd/system/filedrop-feedback.service`:
   ```ini
   [Unit]
   Description=FileDrop feedback server
   After=network.target

   [Service]
   EnvironmentFile=/etc/filedrop-feedback.env
   WorkingDirectory=/opt/filedrop
   ExecStart=/opt/filedrop/.venv/bin/python -m feedback_server --host 127.0.0.1 --port 8095
   User=filedrop
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```
   Then run `systemctl enable --now filedrop-feedback`.
4. In nginx, next to the static site config in `site/README.md`, send the form and admin paths to it:
   ```nginx
   location /api/   { proxy_pass http://127.0.0.1:8095; proxy_set_header Host $host; proxy_set_header X-Forwarded-For $remote_addr; client_max_body_size 6m; }
   location /admin  { proxy_pass http://127.0.0.1:8095; proxy_set_header Host $host; proxy_set_header X-Forwarded-For $remote_addr; }
   ```
5. Back up `/var/lib/filedrop-feedback` with your normal server backups.

## Spam protection

On by default:
- a hidden "honeypot" field that only bots fill in;
- a minimum time between opening and sending a form;
- 5 submissions per IP address per form per 10 minutes;
- a same-site origin check.

For stronger protection, add [Cloudflare Turnstile](https://www.cloudflare.com/products/turnstile/): set `FEEDBACK_TURNSTILE_SECRET`, add the Turnstile widget to the forms, and allow `https://challenges.cloudflare.com` in the site's Content-Security-Policy (`script-src` and `frame-src`).

## Handling reports

Check the inbox at least every two business days, the response time promised on the website.

| Status | Meaning |
| --- | --- |
| **New** | Not looked at yet (counted on each tab) |
| **In progress** | Confirmed and being worked on. Add a private note: what's wrong, which version fixes it |
| **Closed** | Fixed, answered, or won't do. Reply first if they left an email |

1. **Triage new items.** For bugs, try to reproduce them and ask for missing details by email. For ideas, note which Pro feature they support.
2. **Reply** with the "Reply by email" button. Be specific about what happens next.
3. **Close** once released or answered, and mention the version in the note so it shows in the CSV export.
4. **Privacy requests** (contact topic "Privacy request"): find everything from that email, export it if asked, and use **Delete for good**. Do this within 30 days.
5. **Attachments** are downloads only. Open them only if you trust them; only images and text files are accepted.

## Running the beta

1. Pick 10 to 20 sign-ups from the **Beta** tab with a mix of Windows versions and phones (iPhone and Android).
2. Email them the download link and `tests/manual/CHECKLIST.md` as a guide. Ask them to report problems with the feedback page (links from the app prefill the version).
3. After two weeks, send a short survey about the proposed Pro features and price.
4. Mark each beta tester **Closed** with a note once they've given feedback, and keep a list for the free Pro licence promised on the beta page.

## Pro waitlist (CASL)

The waitlist stores each email with the exact consent text and time. When Pro launches, export it from the **Waitlist** tab and include in every email:
- who you are and how to contact you;
- the person's own unsubscribe link (shown in the inbox).

Delete the list after the launch email, as the privacy policy promises.
