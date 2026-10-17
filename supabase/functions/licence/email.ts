// The licence email: a branded HTML version plus a plain-text version for clients that prefer it.
// Email HTML is table-based with inline styles because many mail apps ignore <style> and modern CSS.

export interface LicenceForEmail {
  id: string;
  updates_until: string;
  max_activations: number;
  licence_text: string;
}

export interface EmailContent {
  subject: string;
  text: string;
  html: string;
}

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));

const BLUE = "#1d63ea";
const FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";
const MONO = "ui-monospace,'Cascadia Code',Consolas,'Courier New',monospace";

function step(n: number, html: string): string {
  return `<tr><td style="padding:0 0 12px 0;vertical-align:top;width:34px">
      <div class="fd-num" style="width:26px;height:26px;border-radius:13px;background:${BLUE};color:#ffffff;font:700 13px/26px ${FONT};text-align:center">${n}</div></td>
    <td class="fd-text" style="padding:3px 0 12px 10px;font:15px/1.5 ${FONT};color:#1f2633">${html}</td></tr>`;
}

// The licence body as one flowing block between the BEGIN and END lines, so it wraps evenly at any
// width. FileDrop ignores line breaks inside a pasted licence.
function flowing(licence: string): string {
  const lines = licence.trim().split(/\s*\n\s*/);
  if (lines.length < 3) return esc(licence.trim());
  return `${esc(lines[0])}<br>${esc(lines.slice(1, -1).join(""))}<br>${esc(lines[lines.length - 1])}`;
}

function licenceBlock(r: LicenceForEmail): string {
  return `<tr><td style="padding:6px 0 18px 0">
    <div class="fd-muted" style="font:600 12px/1.4 ${FONT};color:#5b6578;letter-spacing:.04em;text-transform:uppercase;padding-bottom:6px">
      Licence ${esc(r.id)} &middot; updates until ${esc(r.updates_until)}</div>
    <div class="fd-code" style="background:#f3f6fb;border:1px solid #d9e1ee;border-radius:10px;padding:14px 16px;font:12.5px/1.55 ${MONO};color:#111827;word-break:break-all">${flowing(r.licence_text)}</div>
  </td></tr>`;
}

export function licenceEmail(websiteUrl: string, rows: LicenceForEmail[]): EmailContent {
  const many = rows.length > 1;
  const max = Math.max(...rows.map((r) => r.max_activations || 3));
  const subject = many ? "Your FileDrop Pro licences" : "Your FileDrop Pro licence";

  const text = `Thank you for buying FileDrop Pro!

To turn on Pro:
1. Open the FileDrop window on your PC (double-click the tray icon).
2. Go to Licence.
3. Paste the whole licence below, including the BEGIN and END lines, and press Activate Pro.

${rows.map((r) => `Licence ${r.id} (updates until ${r.updates_until}):\n\n${r.licence_text}`).join("\n\n")}

- Use ${many ? "each licence" : "it"} on up to ${max} PCs. To move Pro to a new PC, choose "Remove from this PC" on the old one first.
- Keep this email: you'll need the licence if you reinstall Windows. Lost it? ${websiteUrl}/licence.html

Need help? ${websiteUrl}/contact.html
`;

  const html = `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
<title>${subject}</title>
<style>
  @media (prefers-color-scheme: dark) {
    .fd-bg { background:#05070c !important; }
    .fd-card { background:#0f141f !important; border-color:#1d2538 !important; }
    .fd-text, .fd-title { color:#edf2ff !important; }
    .fd-muted { color:#8a96b0 !important; }
    .fd-code { background:#05070c !important; border-color:#24304a !important; color:#dbe6ff !important; }
    .fd-rule { border-color:#1d2538 !important; }
  }
  @media (max-width: 600px) { .fd-pad { padding-left:20px !important; padding-right:20px !important; } }
</style></head>
<body class="fd-bg" style="margin:0;padding:0;background:#eef2f8">
<div style="display:none;max-height:0;overflow:hidden">Your FileDrop Pro licence is inside. Paste it into FileDrop to unlock Pro.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="fd-bg" style="background:#eef2f8"><tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px">

  <tr><td style="background:#05070c;border-radius:16px 16px 0 0;padding:22px 32px" class="fd-pad">
    <table role="presentation" cellpadding="0" cellspacing="0"><tr>
      <td style="width:32px;height:32px;border-radius:8px;background:${BLUE};color:#ffffff;font:800 18px/32px ${FONT};text-align:center">&#8593;</td>
      <td style="padding-left:10px;font:800 17px/1 ${FONT};color:#ffffff;letter-spacing:.06em">FILEDROP</td>
      <td style="padding-left:8px"><span style="display:inline-block;padding:3px 8px;border-radius:6px;background:${BLUE};color:#ffffff;font:700 11px/1.2 ${FONT};letter-spacing:.06em">PRO</span></td>
    </tr></table>
  </td></tr>

  <tr><td class="fd-card fd-pad" style="background:#ffffff;border:1px solid #dfe5ef;border-top:0;border-radius:0 0 16px 16px;padding:30px 32px 26px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr><td class="fd-title" style="font:800 24px/1.25 ${FONT};color:#0b1220;padding-bottom:8px">Thank you for buying FileDrop Pro!</td></tr>
      <tr><td class="fd-muted" style="font:15px/1.55 ${FONT};color:#5b6578;padding-bottom:22px">Unlimited accounts and scheduled backups are one paste away.</td></tr>
      <tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        ${step(1, "Open the FileDrop window on your PC <span class=\"fd-muted\" style=\"color:#5b6578\">(double-click the tray icon)</span>.")}
        ${step(2, "Go to <b>Licence</b>.")}
        ${step(3, `Paste the whole licence below, including the BEGIN and END lines, and press <b>Activate Pro</b>.`)}
      </table></td></tr>
      ${rows.map(licenceBlock).join("")}
      <tr><td class="fd-rule" style="border-top:1px solid #e5eaf2;padding-top:18px">
        <p class="fd-text" style="margin:0 0 8px;font:14px/1.55 ${FONT};color:#1f2633">&#10003;&nbsp; Use ${many ? "each licence" : "it"} on up to <b>${max} PCs</b>. To move Pro, choose <b>Remove from this PC</b> on the old one first.</p>
        <p class="fd-text" style="margin:0 0 20px;font:14px/1.55 ${FONT};color:#1f2633">&#10003;&nbsp; Keep this email. You'll need the licence if you reinstall Windows.</p>
        <a href="${esc(websiteUrl)}/contact.html" style="display:inline-block;background:${BLUE};color:#ffffff;text-decoration:none;font:700 14px/1 ${FONT};padding:12px 18px;border-radius:10px">Get help</a>
      </td></tr>
    </table>
  </td></tr>

  <tr><td class="fd-muted" style="padding:18px 8px 0;font:12.5px/1.6 ${FONT};color:#6b7487;text-align:center">
    Lost this email? <a href="${esc(websiteUrl)}/licence.html" style="color:${BLUE}">Re-send your licence</a>.<br>
    FileDrop &middot; Made in Canada. Payments are handled by Paddle, our reseller.
  </td></tr>

</table></td></tr></table>
</body></html>`;

  return { subject, text, html };
}
