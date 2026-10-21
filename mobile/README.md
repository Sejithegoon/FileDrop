# WiFiDrop phone app

> **On hold (October 2026).** Parked to focus on the PC app. Status when paused: everything below works in the
> web preview and in Expo Go test mode; the Android native module compiles; the iPhone (Swift) side has never been
> built. To resume: `npm install`, then the "Building for phones" steps.

iPhone and Android app for WiFiDrop, built with Expo (React Native, TypeScript). It talks to the WiFiDrop
PC app on the same Wi-Fi through the PC's `/api/v1` (see `app/api/lan.py`), never through the internet.

## How it connects

- **Pairing.** The PC's QR code holds its web link plus `?wd=1&pin=…&id=…`. `pin` is the SHA-256 of the PC's
  public key (`app/core/tls.py`, `public_key_pin`). The app trusts exactly that key instead of certificate
  authorities, so there's no "not private" warning and no one else on the Wi-Fi can pretend to be the PC.
- **Found on the Wi-Fi.** The PC announces `_wifidrop._tcp` (`app/core/discovery.py`). Pairing that way shows
  a short code the person checks against the PC's Dashboard (`pin_code` on the PC, `pinCode` here).
- **Sign-in.** `client: "app"` logins get a token (kept in the Keychain / Android Keystore) instead of a cookie.
- **Native code.** `modules/wifidrop-net` (Swift + Kotlin) does the pinned HTTPS and the discovery. Because of
  it, the app runs as a *development build*, not inside Expo Go.
- **Demo.** "Try the demo" runs a pretend PC inside the app (`src/api/demo.ts`): for App Store reviewers, for
  screenshots, and for the web preview.

## Layout

| Path | What |
| --- | --- |
| `src/app/` | Screens (Expo Router): connect, scan, confirm, sign-in, password, files, settings |
| `src/api/` | PC API client, transports (pinned / demo), reply types |
| `src/state/` | Paired PCs and tokens, session, discovery, live updates |
| `src/lib/` | Pure helpers (QR parsing, pairing code, formatting), tested with Node |
| `modules/wifidrop-net/` | Native module |
| `scripts/make_icons.py` | Draws the icons from WiFiDrop's mark |

## Commands

```
npm install
npm test            # unit tests (Node)
npm run typecheck
npx expo lint
npx expo start --web   # screens in a browser, demo only
```

## Building for phones (in Expo's cloud, no Mac needed)

```
npx eas-cli@latest login
npx eas-cli@latest init                                  # once: links the project to your Expo account
npx eas-cli@latest build --profile development --platform android   # APK to install on an Android phone
npx eas-cli@latest device:create                         # once per iPhone, for development builds
npx eas-cli@latest build --profile development --platform ios       # needs the Apple Developer Program
npx expo start --dev-client                              # then open the installed app; it loads this code
```

The phone and the PC running WiFiDrop 0.2+ (with HTTPS on) must be on the same Wi-Fi.
