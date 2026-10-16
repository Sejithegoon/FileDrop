# FileDrop website

A static site: plain HTML, one stylesheet and three small scripts. There is no build step and no third-party requests, so it works on any web host, including a Canadian server.

## Pages

| File | What it is |
| --- | --- |
| `index.html` | Home: hero, three steps, clickable admin and phone tours, features, privacy promise |
| `features.html` | What works today, with zoomable screenshots; planned Pro features marked |
| `pricing.html` | "How many people?" picker, Free vs Pro, CASL-compliant waitlist form |
| `feedback.html`, `beta.html` | Bug reports, ideas and questions (optional screenshot); beta sign-up |
| `download.html` | Version, requirements, install steps, SmartScreen note, checksum with copy button |
| `guide.html` | Setup guide: storage folder, users, phones, the HTTPS warning, troubleshooting |
| `faq.html` | Searchable FAQ |
| `contact.html` | Contact form (general, partnership, press, privacy requests) |
| `changelog.html`, `404.html` | Changelog and error page |
| `privacy.html`, `terms.html`, `refunds.html` | **Drafts for legal review** (see below) |
| `update.json` | Version feed the app checks for "update available" |
| `_headers` | Security headers for Cloudflare Pages or Netlify |

Features: light and dark mode (follows the device, with a toggle that remembers the choice), scroll and hover animations that switch off for people who prefer reduced motion, keyboard-accessible tours and zoom, and text contrast that meets WCAG AA in both themes.

## Before you publish

1. **`assets/js/config.js`**: set `downloadUrl`, `sha256`, `downloadSize` and `supportEmail`. Empty values show "coming soon" text, so nothing looks broken. Forms post to `apiBase` (default `/api`, served by `feedback_server/`).
2. **`update.json`**: replace `REPLACE-WITH-YOUR-DOMAIN`, then point the app at `https://<your-domain>/update.json` (`update_feed_url` in `app/core/settings.py`, or `FILEDROP_UPDATE_FEED`) and rebuild.
3. **Legal pages**: fill in every `[square bracket]`: legal name, city, province, privacy officer and email, hosting provider, payment provider, and retention periods. Have a Canadian lawyer review them (PIPEDA, Quebec Law 25, CASL, consumer protection), then remove the draft banners. Add a French version before selling in Quebec.
4. **Name check**: search trademarks and domains for "FileDrop" before buying a domain.

## Hosting

### Any web server (for example a Canadian VPS with nginx)

Upload the contents of `site/` to the web root, and run the form server from `feedback_server/` (its README has the systemd and nginx setup). Add these headers (the same as `_headers`):

```nginx
server {
    listen 443 ssl http2;
    server_name example.ca;
    root /var/www/filedrop;
    index index.html;
    error_page 404 /404.html;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self' https:; frame-ancestors 'none'; base-uri 'self'" always;
    add_header Strict-Transport-Security "max-age=31536000" always;

    location = /update.json { add_header Cache-Control "no-cache"; add_header Access-Control-Allow-Origin "*"; }
    location /assets/ { expires 7d; }
}
```

Use a free Let's Encrypt certificate for HTTPS.

### Cloudflare Pages (free)

Connect the GitHub repo, set **Build command** to empty and **Build output directory** to `site`. `_headers` is applied automatically. Note: Cloudflare serves from data centres worldwide. If you promise "hosted in Canada", use a Canadian host and update the privacy policy's hosting section.

## Preview locally

```bash
.venv/Scripts/python -m http.server 8090 --directory site
```

Then open http://127.0.0.1:8090.

## Editing

- The header and footer repeat in every page; change navigation in all of them.
- Screenshots in `assets/img/` come from a demo copy of FileDrop with made-up users, taken at 2x (desktop) and 3x (phone) as WebP. Retake them when the app's look changes.

## When you release a new version

1. Bump `__version__` in `app/__init__.py` and build with `build/build.ps1`.
2. Upload the installer and update `config.js` (`version`, `releaseDate`, `downloadUrl`, `sha256`, `downloadSize`).
3. Update `update.json` (`version`, `notes`) so existing installs see the update.
4. Add an entry to `changelog.html`.
