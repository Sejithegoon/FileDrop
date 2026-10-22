# Creator beta outreach

Two emails for inviting small YouTubers to test WiFiDrop:

| File | When | Subject |
| --- | --- | --- |
| `1-invite.html` | First contact | Beta invite: a private phone backup app for Windows |
| `2-welcome.html` | After they reply "I'm in" | You're in! Your WiFiDrop beta details |

Who it's for: people with a Windows laptop or PC that has lots of free space, who want to back up their phone's
photos, videos and files without the cloud.

## Easiest: the fill-in page

1. Double-click **`compose.html`**. It opens in your browser.
2. Pick **1 · Invite** or **2 · They said yes**, and fill in the boxes (name, their video, or their licence). The
   preview updates as you type; anything still missing is highlighted in yellow.
3. In Gmail click **Compose**, set **From** to `hello@wifidrop.ca`, and put their email in **To**.
4. Click **Copy subject** and paste it into **Subject**.
5. Click **Copy email**, click in the message box and press **Ctrl+V**. Check it, then **Send**.

Changed the wording in `1-invite.html` or `2-welcome.html`? Run `python marketing/creator-outreach/build_compose.py`
to update `compose.html`.

## By hand (without the fill-in page)

Gmail can't take an HTML file directly, but copying the page keeps the design:

1. Double-click the `.html` file. It opens in Chrome or Edge.
2. Click anywhere on the page, press **Ctrl+A** (select all), then **Ctrl+C** (copy).
3. In Gmail, click **Compose**, set **From** to `hello@wifidrop.ca`, click in the message area and press **Ctrl+V**.
4. Fill in the subject and replace every **[BRACKET]** with the real details.
5. Send it to yourself first and check it on your phone, then send it for real.

### Save them as Gmail templates (do this once)

1. Gmail: ⚙️ → **See all settings** → **Advanced** → **Templates: Enable** → **Save Changes**.
2. Paste an email into a new Compose (steps above), leaving the [BRACKETS] in.
3. In the Compose window click **⋮** (bottom right) → **Templates** → **Save draft as template** → **Save as new template**.
4. Next time: Compose → **⋮** → **Templates** → pick it, then replace the [BRACKETS].

## Before message 2: make their licence

1. Go to https://wifidrop.ca/admin.html, sign in and open the **Licences** tab.
2. Click **Issue licence**. Enter the creator's email in **Customer email** and something like `Beta: <channel name>`
   in **Private note**. Leave the other boxes as they are, then click **Issue licence**.
3. The licence opens. Click **Copy licence** and paste it into the `[LICENCE KEY]` box in message 2.
4. Promised giveaway licences? Issue those the same way (note: `Giveaway: <channel name>`) and send them when the
   creator asks, one per winner.

The email promises 2 extra licences for giveaways. If you'd rather not, delete that line before sending.

## Plain-text versions (YouTube "business enquiries", Instagram or X DMs)

### Message 1

> Hi [Name], We watched your video on [video topic] and liked [one specific thing].
>
> We're building WiFiDrop, a small Windows app that turns a laptop with lots of free space into a private backup for
> your phone: photos, videos and files go straight to the PC over Wi-Fi. No cloud, no monthly fee.
>
> We're picking a few creators to test the beta before launch. You'd get WiFiDrop Pro free (normally CA$29.99), and
> you're welcome to make a video about it, as honest as you like.
>
> Interested? Reply "I'm in" and we'll send the details. Not interested? No worries, we won't message again.
>
> The WiFiDrop team · hello@wifidrop.ca · wifidrop.ca

### Message 2

> You're in, [Name]! Thanks for testing the WiFiDrop beta.
>
> What it is: WiFiDrop turns a Windows PC with lots of space into a private backup for phones. Open a web page on any
> phone on the same Wi-Fi and send photos, videos and files straight to the PC. Nothing goes to the cloud.
>
> Your free Pro licence: [LICENCE KEY]
>
> Get started:
> 1. Download from https://wifidrop.ca/download.html (Windows 10 or 11).
> 2. Run the installer. If Windows says "Windows protected your PC", click More info, then Run anyway (the beta isn't
>    code-signed yet).
> 3. Pick where files are saved, then open Licence and paste the licence.
> 4. Add an account under Users, scan the QR code on the Dashboard with your phone, and start sending photos.
>
> Videos: make whatever you like, and be as honest as you want. No script, no approval, no need to show us first. Two
> small asks: say you got it free for testing (required for creators in Canada and the US), and link wifidrop.ca.
>
> It's a beta, so if anything breaks, just reply with what happened. No deadline.
>
> Thanks! The WiFiDrop team · hello@wifidrop.ca

## Tips

- Personalise the first line every time. Mention a real video of theirs; it's the difference between a reply and spam.
- Email only addresses creators publish for business enquiries (Canada's anti-spam law, CASL). Keep the "Not
  interested? Reply 'no thanks'" line.
- Send a few a day, not dozens at once (Resend's free plan allows about 100 a day).
- Follow up once after about a week if there's no reply, then stop.
- Viewer discount codes: the checkout doesn't accept codes yet. Ask to have a code box (or a code link) added to the
  website first, then add a code to message 2.
