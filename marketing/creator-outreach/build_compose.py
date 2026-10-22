"""Builds compose.html: a fill-in page for the two outreach emails.

The emails themselves live in 1-invite.html and 2-welcome.html. After editing either, run:
    python marketing/creator-outreach/build_compose.py
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def body_of(name: str) -> str:
    html = (HERE / name).read_text(encoding="utf-8")
    return re.search(r"<body[^>]*>(.*)</body>", html, re.S).group(1).strip()


def subjects_of(name: str) -> list[str]:
    html = (HERE / name).read_text(encoding="utf-8")
    found = re.findall(r"^\s+- (.+)$", html, re.M) or re.findall(r"Subject: (.+)$", html, re.M)
    return [s.strip() for s in found]


TEMPLATES = {
    "invite": {"body": body_of("1-invite.html"), "subjects": subjects_of("1-invite.html")},
    "welcome": {"body": body_of("2-welcome.html"), "subjects": subjects_of("2-welcome.html")},
}

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WiFiDrop outreach</title>
<style>
  :root { --bg:#f2f5fb; --card:#fff; --ink:#0b1220; --muted:#5b6782; --line:#dbe2f0; --blue:#2f7bff; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system,"Segoe UI",Roboto,Arial,sans-serif; }
  header { background:#0b1220; color:#fff; padding:16px 24px; display:flex; align-items:center; gap:12px; }
  header b { font-size:18px; }
  .logo { width:30px; height:30px; border-radius:8px; background:var(--blue); display:grid; place-items:center; font-weight:bold; }
  main { display:grid; grid-template-columns:minmax(280px,380px) 1fr; gap:20px; padding:20px; max-width:1200px; margin:0 auto; }
  @media (max-width:860px) { main { grid-template-columns:1fr; } }
  .card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px; }
  .tabs { display:flex; gap:6px; margin-bottom:14px; }
  .tabs button { flex:1; padding:10px; border:1px solid var(--line); background:#f7f9fd; border-radius:10px; font:inherit; font-weight:600; cursor:pointer; color:var(--ink); }
  .tabs button[aria-selected=true] { background:var(--blue); border-color:var(--blue); color:#fff; }
  label { display:block; font-weight:600; font-size:13px; color:var(--muted); margin:12px 0 5px; }
  input, textarea, select { width:100%; padding:10px 12px; border:1px solid var(--line); border-radius:10px; font:inherit; color:var(--ink); background:#fff; }
  textarea { min-height:150px; font-family:Consolas,monospace; font-size:12px; }
  .hint { font-size:12.5px; color:var(--muted); margin-top:4px; }
  .actions { display:grid; gap:8px; margin-top:18px; }
  .btn { padding:12px; border-radius:10px; border:1px solid var(--line); background:#f7f9fd; font:inherit; font-weight:700; cursor:pointer; color:var(--ink); }
  .btn.primary { background:var(--blue); border-color:var(--blue); color:#fff; }
  .missing { color:#b42318; font-size:13px; margin-top:10px; }
  .steps { margin:16px 0 0; padding-left:20px; color:var(--muted); font-size:13.5px; }
  .preview-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; color:var(--muted); font-size:13px; }
  #preview { border:1px solid var(--line); border-radius:12px; overflow:hidden; background:#fff; }
  .toast { position:fixed; bottom:20px; left:50%; transform:translateX(-50%); background:#0b1220; color:#fff; padding:10px 18px; border-radius:10px; opacity:0; transition:opacity .2s; }
  .toast.show { opacity:1; }
  [hidden] { display:none !important; }
</style>
</head>
<body>
<header><div class="logo">&#8593;</div><b>WiFiDrop creator outreach</b></header>
<main>
  <section class="card">
    <div class="tabs" role="tablist">
      <button type="button" role="tab" data-tab="invite" aria-selected="true">1 &middot; Invite</button>
      <button type="button" role="tab" data-tab="welcome" aria-selected="false">2 &middot; They said yes</button>
    </div>

    <label for="name">Creator's name</label>
    <input id="name" placeholder="e.g. Alex" autocomplete="off">

    <div data-for="invite">
      <label for="video">Their video you watched</label>
      <input id="video" placeholder="e.g. backing up your iPhone without iCloud" autocomplete="off">
      <label for="liked">What you liked about it</label>
      <input id="liked" placeholder="e.g. how simply you explained it" autocomplete="off">
      <div class="hint">Shows up as: "We watched your video on <i>video</i> and liked <i>this</i>."</div>
    </div>

    <div data-for="welcome" hidden>
      <label for="licence">Their Pro licence</label>
      <textarea id="licence" placeholder="Paste from wifidrop.ca/admin.html > Licences > Issue licence > Copy licence"></textarea>
      <label><input type="checkbox" id="giveaway" checked style="width:auto"> Offer 2 extra licences for a giveaway</label>
    </div>

    <label for="subject">Subject</label>
    <select id="subject"></select>

    <div class="missing" id="missing" hidden></div>
    <div class="actions">
      <button class="btn primary" type="button" id="copyEmail">Copy email</button>
      <button class="btn" type="button" id="copySubject">Copy subject</button>
    </div>
    <ol class="steps">
      <li>Fill in the boxes. The preview updates as you type.</li>
      <li>Gmail: <b>Compose</b>, set <b>From</b> to hello@wifidrop.ca, and add their email in <b>To</b>.</li>
      <li><b>Copy subject</b>, paste it into Subject.</li>
      <li><b>Copy email</b>, click in the message box and press <b>Ctrl+V</b>. Send.</li>
    </ol>
  </section>

  <section>
    <div class="preview-head"><span>Preview (what they'll see)</span><span id="which"></span></div>
    <div id="preview"></div>
  </section>
</main>
<div class="toast" id="toast"></div>

<script>
const TEMPLATES = __TEMPLATES__;
const $ = (s) => document.querySelector(s);
let tab = 'invite';

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function fields() {
  return {
    name: $('#name').value.trim(),
    video: $('#video').value.trim(),
    liked: $('#liked').value.trim(),
    licence: $('#licence').value.trim(),
  };
}

function build() {
  const f = fields();
  let html = TEMPLATES[tab].body;
  const fill = (token, value, label) => html = html.split(token).join(value ? esc(value) : `<span style="background:#fff3c4;color:#8a5a00;">${label}</span>`);
  fill('[Name]', f.name, '[Name]');
  fill('[video topic]', f.video, '[video topic]');
  fill('[one specific thing you liked]', f.liked, '[what you liked]');
  html = html.split('[LICENCE KEY]').join(f.licence ? esc(f.licence).replace(/\\r?\\n/g, '<br>') : '<span style="background:#fff3c4;color:#8a5a00;">[LICENCE KEY]</span>');
  if (tab === 'welcome' && !$('#giveaway').checked) {
    html = html.replace(/<tr><td style="padding:6px 0;">[^<]*<b>2 extra Pro licences<\\/b>.*?<\\/td><\\/tr>/, '');
  }
  return html;
}

function missing() {
  const f = fields();
  const need = [];
  if (!f.name) need.push("the creator's name");
  if (tab === 'invite' && !f.video) need.push('their video');
  if (tab === 'invite' && !f.liked) need.push('what you liked');
  if (tab === 'welcome' && !/BEGIN/.test(f.licence)) need.push('the licence (BEGIN ... END)');
  return need;
}

function render() {
  $('#preview').innerHTML = build();
  $('#which').textContent = tab === 'invite' ? 'Message 1: first contact' : 'Message 2: after "I\\'m in"';
  const need = missing();
  $('#missing').hidden = need.length === 0;
  $('#missing').textContent = need.length ? 'Still to fill in: ' + need.join(', ') + '.' : '';
}

function setTab(next) {
  tab = next;
  document.querySelectorAll('[role=tab]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
  document.querySelectorAll('[data-for]').forEach((el) => { el.hidden = el.dataset.for !== tab; });
  $('#subject').innerHTML = TEMPLATES[tab].subjects.map((s) => `<option>${esc(s)}</option>`).join('');
  render();
}

function toast(text) {
  $('#toast').textContent = text;
  $('#toast').classList.add('show');
  setTimeout(() => $('#toast').classList.remove('show'), 2200);
}

async function copyRich(html, text) {
  try {
    await navigator.clipboard.write([new ClipboardItem({
      'text/html': new Blob([html], { type: 'text/html' }),
      'text/plain': new Blob([text], { type: 'text/plain' }),
    })]);
    return true;
  } catch {
    // Older browsers / file pages: select the preview and copy it.
    const range = document.createRange();
    range.selectNodeContents($('#preview'));
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    const ok = document.execCommand('copy');
    sel.removeAllRanges();
    return ok;
  }
}

$('#copyEmail').onclick = async () => {
  const need = missing();
  if (need.length && !confirm('Still to fill in: ' + need.join(', ') + '.\\n\\nCopy anyway?')) return;
  const ok = await copyRich(build(), $('#preview').innerText);
  toast(ok ? 'Email copied. Paste it into Gmail with Ctrl+V.' : "Couldn't copy. Select the preview and press Ctrl+C.");
};

$('#copySubject').onclick = async () => {
  try { await navigator.clipboard.writeText($('#subject').value); toast('Subject copied.'); }
  catch { toast("Couldn't copy. Select the subject and press Ctrl+C."); }
};

document.querySelectorAll('[role=tab]').forEach((b) => b.onclick = () => setTab(b.dataset.tab));
['#name', '#video', '#liked', '#licence', '#giveaway'].forEach((s) => $(s).addEventListener('input', render));
setTab('invite');
</script>
</body>
</html>
"""

out = PAGE.replace("__TEMPLATES__", json.dumps(TEMPLATES).replace("</", "<\\/"))
(HERE / "compose.html").write_text(out, encoding="utf-8")
print("Wrote", HERE / "compose.html", "with subjects:", {k: v["subjects"] for k, v in TEMPLATES.items()})
