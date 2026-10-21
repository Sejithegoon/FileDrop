// Admin window: server controls, users, shared folders, file browser, activity, backups, licence.
const $ = s => document.querySelector(s);
const GB = 1024 ** 3;
let page = 'dashboard';
let overview = null;

async function api(url, opts) {
    try {
        return await FD.api('/api' + url, opts);
    } catch (e) {
        if (e.code === 'LOCKED') showLock();
        throw e;
    }
}
const fail = e => FD.toast(e.message, 'err');
const gbOrNull = v => (v === '' || v == null ? null : Math.round(parseFloat(v) * GB));
const quotaText = (used, quota) => quota == null ? `${FD.fmtSize(used)} · no limit` : `${FD.fmtSize(used)} of ${FD.fmtSize(quota)}`;

// ---------- navigation

const PAGES = ['dashboard', 'users', 'shared', 'files', 'activity', 'backups', 'licence', 'about'];

function go(p) {
    if (!PAGES.includes(p)) p = 'dashboard';
    page = p;
    history.replaceState(null, '', '#' + p);
    document.querySelectorAll('#nav button').forEach(b => b.toggleAttribute('aria-current', b.dataset.page === p));
    document.querySelectorAll('[data-view]').forEach(v => { v.hidden = v.dataset.view !== p; });
    ({ dashboard: loadDashboard, users: loadUsers, shared: loadSpaces, files: loadBrowser, activity: loadActivity,
       backups: loadBackups, licence: loadLicence, about: loadAbout })[p]();
    if (p !== 'dashboard') refreshSide();
}

function renderSide(o) {
    const running = o.server.state === 'running';
    $('#feedbackBtn').hidden = !o.feedback_url;
    $('#version').textContent = `v${o.version}`;
    $('#sidePill').className = `pill ${running ? '' : 'bad'}`;
    $('#sideState').textContent = running ? 'Server running' : 'Server stopped';
    if (o.edition) renderEdition(o.edition, o.website_url);
}

function renderEdition(e, website) {
    $('#navEdition').textContent = e.pro ? 'PRO' : 'FREE';
    $('#navEdition').className = `badge ${e.pro ? 'accent' : ''}`;
    if (website) { $('#licBuy').href = `${website}/pricing.html`; $('#licBuy').hidden = false; }
}

async function refreshSide() {
    try { renderSide(await api('/overview')); } catch { markOffline(); }
}
document.querySelectorAll('#nav button').forEach(b => b.onclick = () => go(b.dataset.page));
document.querySelectorAll('[data-goto]').forEach(b => b.onclick = () => go(b.dataset.goto));
window.addEventListener('hashchange', () => { const p = location.hash.slice(1); if (p !== page && $('#lockScreen').hidden) go(p); });

// ---------- dashboard

async function loadDashboard() {
    try { overview = await api('/overview'); } catch (e) { return markOffline(); }
    const o = overview, running = o.server.state === 'running';
    renderSide(o);
    $('#serverState').classList.toggle('running', running);
    $('#serverText').textContent = running ? 'Web server is running' : o.server.state === 'starting' ? 'Starting…' : 'Web server is stopped';
    $('#serverHint').textContent = running
        ? 'People on the same Wi-Fi can open this link or scan the code, then sign in with their account.'
        : 'Nobody can connect while the web server is stopped. Your files are safe.';
    $('#serverUrl').textContent = o.url;
    $('#tlsNote').hidden = !o.server.https;
    if (o.server.https) {
        const fp = o.server.fingerprint || '';
        $('#tlsNote').innerHTML = `${FD.icon('lock')} <b>Secure connection (HTTPS).</b> The first time, phones warn the connection isn't private because WiFiDrop made its own certificate. ` +
            `iPhone: tap <b>Show Details → visit this website</b>. Android: <b>Advanced → Proceed</b>.` +
            (fp ? `<br><span class="muted">Certificate fingerprint: <code title="${fp}">${fp.slice(0, 23)}…</code></span>` : '') +
            (o.server.pin_code ? `<br><span class="muted">WiFiDrop phone app code: <code>${FD.esc(o.server.pin_code)}</code></span>` : '') +
            (o.server.helper_url ? `<br><span class="muted">Typing just <code>${FD.esc(o.server.helper_url)}</code> opens a help page with a button to the secure link.</span>` : '');
    }
    $('#plainNote').hidden = o.server.https;
    $('#httpsToggle').checked = o.server.https;
    $('#httpsToggle').disabled = o.https_forced;
    $('#qr').innerHTML = o.qr;
    $('#qr').classList.toggle('off', !running);
    $('#serverBtnText').textContent = running ? 'Stop web server' : 'Start web server';
    $('#serverBtn').className = running ? 'btn danger' : 'btn primary';
    $('#updateNote').hidden = !o.update;
    if (o.update) $('#updateText').textContent = `WiFiDrop ${o.update.version} is available (you have ${o.version}). ${o.update.notes || ''}`;
    $('#blockedNote').hidden = !o.server.error;
    $('#blockedText').textContent = o.server.error || '';
    $('#allowUploads').checked = !o.uploads_paused;
    $('#allowDownloads').checked = !o.downloads_paused;
    $('#statUsers').textContent = o.counts.users;
    $('#statSessions').textContent = o.counts.sessions;
    $('#statUploads').textContent = o.counts.uploads;
    $('#statStored').textContent = FD.fmtSize(o.files_bytes);
    $('#statFree').textContent = o.storage ? `${FD.fmtSize(o.storage.disk_free)} free on disk` : 'no folder chosen';
    $('#storagePath').textContent = o.storage ? o.storage.root : 'Not chosen yet';
    $('#storageFree').textContent = o.storage ? `${FD.fmtSize(o.storage.disk_free)} free on this drive.` : '';
    $('#changeStorage').hidden = o.storage_override || !o.storage;
    $('#openStorage').hidden = !o.storage;
    $('#setupBrowse').hidden = $('#moveBrowse').hidden = !o.can_browse;
    renderMove(o.move);
    if (!o.storage && !o.storage_override && $('#setup').hidden) openSetup(o);
    loadSessions();
}

function markOffline() {
    $('#sidePill').className = 'pill bad';
    $('#sideState').textContent = 'WiFiDrop not responding';
}

$('#serverBtn').onclick = async () => {
    const running = overview?.server.state === 'running';
    if (running && overview.counts.sessions + overview.counts.uploads > 0 &&
        !await FD.confirmBox('Stop the web server?', `${overview.counts.sessions} device(s) are signed in and ${overview.counts.uploads} upload(s) are running. They will be cut off.`, 'Stop server')) return;
    $('#serverBtn').disabled = true;
    try {
        const s = await api(running ? '/server/stop' : '/server/start', { json: {} });
        if (s.error) FD.toast(s.error, 'err'); else FD.toast(running ? 'Web server stopped' : 'Web server started');
    } catch (e) { fail(e); }
    $('#serverBtn').disabled = false;
    loadDashboard();
};

$('#httpsToggle').onchange = async e => {
    const on = e.target.checked;
    if (!on && !await FD.confirmBox('Turn off HTTPS?',
        'Without HTTPS, anyone on the same network could see passwords and files as they travel. Only do this on your own Wi-Fi or hotspot. Signed-in phones need to open the new http:// link.', 'Turn off HTTPS')) {
        e.target.checked = true;
        return;
    }
    try {
        await api('/https', { json: { enabled: on } });
        FD.toast(on ? 'HTTPS is on. Phones will see a one-time warning.' : 'HTTPS is off');
    } catch (err) { fail(err); e.target.checked = !on; }
    loadDashboard();
};

$('#updateBtn').onclick = () => api('/open-update', { json: {} }).catch(fail);

$('#copyUrl').onclick = async () => {
    try { await navigator.clipboard.writeText($('#serverUrl').textContent); FD.toast('Link copied'); }
    catch { FD.toast('Copy failed. Select the link and copy it.', 'err'); }
};

for (const [id, key] of [['#allowUploads', 'uploads_paused'], ['#allowDownloads', 'downloads_paused']]) {
    $(id).onchange = async e => {
        try {
            await api('/controls', { json: { [key]: !e.target.checked } });
            FD.toast(`${key.startsWith('uploads') ? 'Uploads' : 'Downloads'} ${e.target.checked ? 'allowed' : 'paused'}`);
        } catch (err) { fail(err); e.target.checked = !e.target.checked; }
    };
}

$('#openStorage').onclick = () => api('/open-storage', { json: {} }).catch(fail);

// ---------- storage folder: first-run setup and moving later

// Wires a path box + Browse button to live checks. Returns () => last good check.
function folderPicker(input, browse, info, error) {
    let last = null, timer = null, seq = 0;
    const run = async () => {
        const mine = ++seq;
        error.hidden = true;
        if (!input.value.trim()) { info.textContent = ''; last = null; return; }
        try {
            const c = await api('/storage/check', { json: { path: input.value } });
            if (mine !== seq) return;
            last = c;
            info.innerHTML = `Files will be saved in <b>${FD.esc(c.path)}</b> · ${FD.fmtSize(c.free_bytes)} free` +
                (c.existing_store ? ' · existing WiFiDrop folder' : c.exists ? '' : ' · will be created');
        } catch (e) {
            if (mine !== seq) return;
            last = null;
            info.textContent = '';
            error.textContent = e.message;
            error.hidden = false;
        }
    };
    input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(run, 300); });
    browse.onclick = async () => {
        try {
            const r = await api('/storage/choose', { json: {} });
            if (r.path) { input.value = r.path; run(); }
        } catch (e) { fail(e); }
    };
    return { check: run, result: () => last };
}

const setupPicker = folderPicker($('#setupPath'), $('#setupBrowse'), $('#setupInfo'), $('#setupError'));
const movePicker = folderPicker($('#movePath'), $('#moveBrowse'), $('#moveInfo'), $('#moveError'));

function openSetup(o) {
    $('#setup').hidden = false;
    $('#setupPath').value = o.suggested_root;
    setupPicker.check();
}

$('#setupSave').onclick = async () => {
    await setupPicker.check();
    if (!setupPicker.result()) return;
    $('#setupSave').disabled = true;
    try {
        const r = await api('/storage/setup', { json: { path: $('#setupPath').value } });
        $('#setup').hidden = true;
        FD.toast(`Files will be saved in ${r.path}`);
        loadDashboard();
    } catch (e) {
        $('#setupError').textContent = e.message;
        $('#setupError').hidden = false;
    }
    $('#setupSave').disabled = false;
};

$('#changeStorage').onclick = () => {
    $('#movePath').value = '';
    $('#moveInfo').textContent = '';
    $('#moveError').hidden = true;
    $('#moveDlg').showModal();
    $('#movePath').focus();
};
$('#moveCancel').onclick = () => $('#moveDlg').close();

$('#moveGo').onclick = async () => {
    await movePicker.check();
    if (!movePicker.result()) return;
    $('#moveGo').disabled = true;
    try {
        const m = await api('/storage/move', { json: { path: $('#movePath').value } });
        $('#moveDlg').close();
        renderMove(m);
        pollMove();
    } catch (e) {
        $('#moveError').textContent = e.message;
        $('#moveError').hidden = false;
    }
    $('#moveGo').disabled = false;
};

let lastMoveState = null;
function renderMove(m) {
    if (!m) return;
    const moving = m.state === 'moving';
    $('#moveProgress').hidden = !moving && m.state !== 'error';
    $('#changeStorage').disabled = moving;
    if (moving) {
        const pct = m.total_bytes ? (m.copied_bytes / m.total_bytes) * 100 : 0;
        $('#moveText').textContent = `Moving files to ${m.target}… ${FD.fmtSize(m.copied_bytes)} of ${FD.fmtSize(m.total_bytes)}. Uploads are paused until it finishes.`;
        $('#moveBar').style.width = pct + '%';
    } else if (m.state === 'error') {
        $('#moveText').textContent = `Moving failed, nothing changed: ${m.error}`;
        $('#moveBar').style.width = '0%';
    }
    if (lastMoveState === 'moving' && m.state === 'done') FD.toast(`Files moved to ${m.target}`);
    if (lastMoveState === 'moving' && m.state === 'error') FD.toast('Moving files failed. Nothing changed.', 'err');
    lastMoveState = m.state;
}

async function pollMove() {
    let m;
    try { m = await api('/storage/move'); } catch { return; }
    renderMove(m);
    if (m.state === 'moving') setTimeout(pollMove, 700);
    else loadDashboard();
}

async function loadSessions() {
    let data;
    try { data = await api('/sessions'); } catch { return; }
    $('#sessionsEmpty').hidden = data.sessions.length > 0;
    $('#sessionsTbl').innerHTML = data.sessions.length ? `<tr><th>User</th><th>Device</th><th>IP</th><th>Last active</th><th></th></tr>` +
        data.sessions.map(s => `<tr><td class="strong">${FD.esc(s.display_name)} <span class="muted small">@${FD.esc(s.username)}</span></td>
            <td class="muted small">${FD.esc(device(s.user_agent))}</td><td><code>${FD.esc(s.ip)}</code></td>
            <td class="muted">${FD.fmtAgo(s.last_seen_at)}</td>
            <td class="actions"><button class="btn ghost small danger" data-revoke="${s.id}">Sign out</button></td></tr>`).join('') : '';
    $('#sessionsTbl').querySelectorAll('[data-revoke]').forEach(b => b.onclick = async () => {
        try { await api(`/sessions/${b.dataset.revoke}/revoke`, { json: {} }); FD.toast('Device signed out'); loadDashboard(); } catch (e) { fail(e); }
    });
    $('#uploadsCard').hidden = !data.uploads.length;
    $('#uploadsTbl').innerHTML = `<tr><th>File</th><th>User</th><th>Folder</th><th class="num">Progress</th><th></th></tr>` +
        data.uploads.map(u => `<tr><td class="strong">${FD.esc(u.name)}</td><td>@${FD.esc(u.username)}</td><td class="muted">${FD.esc(u.space_name)}</td>
            <td class="num">${FD.fmtSize(u.received)} / ${FD.fmtSize(u.size)}</td>
            <td class="actions"><button class="btn ghost small danger" data-cancel="${u.id}">Cancel</button></td></tr>`).join('');
    $('#uploadsTbl').querySelectorAll('[data-cancel]').forEach(b => b.onclick = async () => {
        try { await api(`/uploads/${b.dataset.cancel}/cancel`, { json: {} }); FD.toast('Upload cancelled'); loadDashboard(); } catch (e) { fail(e); }
    });
}

function device(ua) {
    if (!ua) return 'Unknown';
    const os = /iPhone/.test(ua) ? 'iPhone' : /iPad/.test(ua) ? 'iPad' : /Android/.test(ua) ? 'Android' : /Windows/.test(ua) ? 'Windows' : /Mac OS/.test(ua) ? 'Mac' : /Linux/.test(ua) ? 'Linux' : 'Device';
    const br = /Edg\//.test(ua) ? 'Edge' : /CriOS|Chrome\//.test(ua) ? 'Chrome' : /FxiOS|Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : '';
    return br ? `${br} on ${os}` : os;
}

setInterval(() => { if (page === 'dashboard' && !document.hidden) loadDashboard(); }, 3000);

// ---------- live updates: reload the open page when anything changes (someone signs in,
// uploads, deletes...). Skipped while you're typing or a dialog is open, then caught up.

let adminVersion = null;
async function checkForChanges() {
    if (document.hidden || !$('#lockScreen').hidden || document.querySelector('dialog[open]')) return;
    const active = document.activeElement;
    if (active && active.matches('input, textarea, select') && active.closest('main')) return;
    try {
        const { version } = await api('/changes');
        if (adminVersion !== null && version !== adminVersion) {
            const reload = { users: loadUsers, shared: loadSpaces, activity: loadActivity, backups: loadBackups, licence: loadLicence,
                files: loadBrowser }[page];
            if (reload) await reload();
            refreshSide();
        }
        adminVersion = version;
    } catch { /* locked or offline; tried again shortly */ }
}
setInterval(checkForChanges, 3000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) checkForChanges(); });

// Admin downloads: same check as the phone page, so a deleted file gives a clear message.
document.addEventListener('click', async e => {
    const a = e.target.closest('#fileList a[download]');
    if (!a) return;
    e.preventDefault();
    try {
        const r = await fetch(a.href, { headers: { Range: 'bytes=0-0', 'X-WiFiDrop': '1' } });
        if (r.ok) {
            const go = Object.assign(document.createElement('a'), { href: a.href, download: '' });
            document.body.appendChild(go); go.click(); go.remove();
            return;
        }
        FD.toast(r.status === 404 ? 'That file was deleted or moved. The list has been refreshed.' : "Couldn't download that file.", 'err');
        if (browse.spaceId) openBrowse(browse.spaceId, browse.folderId);
    } catch { FD.toast("Couldn't download that file.", 'err'); }
});

$('#feedbackBtn').onclick = () => api('/open-feedback', { json: {} }).catch(fail);

$('#quitBtn').onclick = async () => {
    if (!await FD.confirmBox('Quit WiFiDrop?', 'The web server stops for everyone until you open WiFiDrop again.', 'Quit')) return;
    try { await api('/quit', { json: {} }); } catch { /* window closes */ }
};

// ---------- users

async function loadUsers() {
    let data;
    try { data = await api('/users'); } catch (e) { return fail(e); }
    $('#usersEmpty').hidden = data.users.length > 0;
    api('/licence').then(e => {
        $('#userLimitNote').hidden = e.max_users == null || data.users.length < e.max_users - 1;
        $('#userLimitText').textContent = data.users.length >= (e.max_users ?? Infinity)
            ? `You're using all ${e.max_users} accounts in WiFiDrop Free. Pro has unlimited accounts.`
            : `${data.users.length} of ${e.max_users} accounts used in WiFiDrop Free.`;
    }).catch(() => {});
    $('#usersTbl').innerHTML = data.users.length ? `<tr><th>User</th><th>Role</th><th>Status</th><th>Storage</th><th>Last active</th><th></th></tr>` +
        data.users.map(u => {
            const status = u.status === 'active'
                ? (u.locked_until && u.locked_until > Date.now() ? '<span class="badge warn">locked out</span>' : '<span class="badge ok">active</span>')
                : '<span class="badge bad">suspended</span>';
            return `<tr data-id="${u.id}">
                <td><div class="strong">${FD.esc(u.display_name)}</div><div class="muted small">@${FD.esc(u.username)}${u.must_change_password ? ' · must set password' : ''}</div></td>
                <td>${u.role === 'admin' ? '<span class="badge accent">admin</span>' : '<span class="badge">user</span>'}</td>
                <td>${status}</td>
                <td class="muted small">${quotaText(u.used_bytes, u.quota_bytes)}</td>
                <td class="muted small">${u.active_sessions ? `<b style="color:var(--ok)">online</b>` : FD.fmtAgo(u.last_seen_at)}</td>
                <td class="actions">
                    <button class="btn ghost small" data-act="edit" title="Edit">${FD.icon('edit')}</button>
                    <button class="btn ghost small" data-act="password" title="Reset password">${FD.icon('key')}</button>
                    <button class="btn ghost small" data-act="toggle">${u.status === 'active' ? 'Suspend' : 'Enable'}</button>
                    <button class="btn ghost small danger" data-act="delete" title="Delete">${FD.icon('trash')}</button>
                </td></tr>`;
        }).join('') : '';
    $('#usersTbl').querySelectorAll('tr[data-id]').forEach(tr => {
        const u = data.users.find(x => x.id === tr.dataset.id);
        tr.querySelector('[data-act=edit]').onclick = () => editUser(u);
        tr.querySelector('[data-act=password]').onclick = () => resetPassword(u);
        tr.querySelector('[data-act=toggle]').onclick = () => toggleUser(u);
        tr.querySelector('[data-act=delete]').onclick = () => deleteUser(u);
    });
}

$('#addUserBtn').onclick = async () => {
    const v = await FD.dialog({
        title: 'Add user', ok: 'Create user',
        body: 'Give them the username and temporary password. They pick their own password at first sign-in.',
        fields: [
            { name: 'username', label: 'Username (letters, digits, . - _)', placeholder: 'e.g. sam' },
            { name: 'display_name', label: 'Display name', placeholder: 'e.g. Sam Smith' },
            { name: 'password', label: 'Temporary password (8+ characters)', value: tempPassword() },
            { name: 'role', label: 'Role', type: 'select', value: 'user', options: [{ value: 'user', label: 'User: own files + shared folders they are added to' }, { value: 'admin', label: 'Admin: also manages every shared folder' }] },
            { name: 'quota', label: 'Storage limit in GB (blank = no limit)', type: 'number', attrs: 'min="0" step="0.5"' },
            { name: 'must_change', label: 'Ask them to choose a new password at first sign-in', type: 'checkbox', value: true },
        ],
    });
    if (!v) return;
    try {
        await api('/users', { json: { username: v.username, display_name: v.display_name, password: v.password, role: v.role, quota_bytes: gbOrNull(v.quota), must_change_password: v.must_change } });
        FD.toast(`User @${v.username.trim().toLowerCase()} created`);
        loadUsers();
    } catch (e) { fail(e); }
};

function tempPassword() {
    const words = ['maple', 'river', 'cloud', 'tiger', 'lemon', 'stone', 'pixel', 'comet', 'ocean', 'cedar'];
    const pick = () => words[crypto.getRandomValues(new Uint32Array(1))[0] % words.length];
    return `${pick()}-${pick()}-${crypto.getRandomValues(new Uint32Array(1))[0] % 90 + 10}`;
}

async function editUser(u) {
    const v = await FD.dialog({
        title: `Edit @${u.username}`, ok: 'Save',
        fields: [
            { name: 'display_name', label: 'Display name', value: u.display_name },
            { name: 'role', label: 'Role', type: 'select', value: u.role, options: [{ value: 'user', label: 'User' }, { value: 'admin', label: 'Admin' }] },
            { name: 'quota', label: 'Storage limit in GB (blank = no limit)', type: 'number', value: u.quota_bytes == null ? '' : +(u.quota_bytes / GB).toFixed(2), attrs: 'min="0" step="0.5"' },
        ],
    });
    if (!v) return;
    try {
        await api(`/users/${u.id}`, { method: 'PATCH', json: { display_name: v.display_name, role: v.role, quota_bytes: gbOrNull(v.quota), set_quota: true } });
        FD.toast('Saved');
        loadUsers();
    } catch (e) { fail(e); }
}

async function resetPassword(u) {
    const v = await FD.dialog({
        title: `Reset password for @${u.username}`, ok: 'Reset password',
        body: 'They will be signed out everywhere.',
        fields: [
            { name: 'password', label: 'New temporary password', value: tempPassword() },
            { name: 'must_change', label: 'Ask them to choose a new password at next sign-in', type: 'checkbox', value: true },
        ],
    });
    if (!v) return;
    try { await api(`/users/${u.id}/password`, { json: { password: v.password, must_change_password: v.must_change } }); FD.toast('Password reset'); loadUsers(); }
    catch (e) { fail(e); }
}

async function toggleUser(u) {
    const suspend = u.status === 'active';
    if (suspend && !await FD.confirmBox(`Suspend @${u.username}?`, 'They are signed out right away and can\'t sign in until you enable them again. Their files stay.', 'Suspend')) return;
    try { await api(`/users/${u.id}`, { method: 'PATCH', json: { status: suspend ? 'suspended' : 'active' } }); FD.toast(suspend ? 'User suspended' : 'User enabled'); loadUsers(); }
    catch (e) { fail(e); }
}

async function deleteUser(u) {
    const v = await FD.dialog({
        title: `Delete @${u.username}?`, ok: 'Delete user for good', danger: true,
        body: `This deletes the account and <b>all of their private files</b> (${FD.fmtSize(u.used_bytes)}). Files they added to shared folders stay. Type <b>${FD.esc(u.username)}</b> to confirm.`,
        fields: [{ name: 'confirm', label: 'Username', placeholder: u.username }],
    });
    if (!v) return;
    try { await api(`/users/${u.id}/delete`, { json: { confirm: v.confirm } }); FD.toast('User deleted'); loadUsers(); }
    catch (e) { fail(e); }
}

// ---------- shared folders

async function loadSpaces() {
    let data;
    try { data = await api('/spaces'); } catch (e) { return fail(e); }
    const shared = data.spaces.filter(s => s.kind === 'shared');
    const people = data.users.filter(u => u.role !== 'admin');
    $('#spacesEmpty').hidden = shared.length > 0;
    $('#spacesGrid').innerHTML = shared.map(s => `
        <div class="card" data-id="${s.id}">
            <div class="card-head"><h2>${FD.icon('share')} ${FD.esc(s.name)}</h2>
                <div class="row-actions">
                    <button class="btn ghost small icon-only" data-act="edit" title="Rename or set limit">${FD.icon('edit')}</button>
                    <button class="btn ghost small icon-only danger" data-act="delete" title="Delete">${FD.icon('trash')}</button>
                </div></div>
            <p class="muted small">${quotaText(s.used_bytes, s.quota_bytes)}</p>
            <div style="margin-top:10px">${people.length ? people.map(u => {
                const m = s.members.find(x => x.user_id === u.id);
                return `<div class="member-row"><span><b>${FD.esc(u.display_name)}</b> <span class="muted small">@${FD.esc(u.username)}</span></span>
                    <select class="input" data-user="${u.id}">
                        ${[['', 'No access'], ['view', 'View'], ['upload', 'Upload'], ['manage', 'Manage']].map(([val, label]) =>
                            `<option value="${val}"${(m ? m.level : '') === val ? ' selected' : ''}>${label}</option>`).join('')}
                    </select></div>`;
            }).join('') : '<p class="muted small">Add users first, then give them access here.</p>'}</div>
        </div>`).join('');
    $('#spacesGrid').querySelectorAll('.card[data-id]').forEach(card => {
        const s = shared.find(x => x.id === card.dataset.id);
        card.querySelectorAll('select[data-user]').forEach(sel => sel.onchange = async () => {
            try { await api(`/spaces/${s.id}/members/${sel.dataset.user}`, { method: 'PUT', json: { level: sel.value || null } }); FD.toast('Access updated'); }
            catch (e) { fail(e); loadSpaces(); }
        });
        card.querySelector('[data-act=edit]').onclick = () => editSpace(s);
        card.querySelector('[data-act=delete]').onclick = () => deleteSpace(s);
    });
}

$('#addSpaceBtn').onclick = async () => {
    const v = await FD.dialog({
        title: 'New shared folder', ok: 'Create',
        fields: [
            { name: 'name', label: 'Name', placeholder: 'e.g. Family photos' },
            { name: 'quota', label: 'Storage limit in GB (blank = no limit)', type: 'number', attrs: 'min="0" step="0.5"' },
        ],
    });
    if (!v) return;
    try { await api('/spaces', { json: { name: v.name, quota_bytes: gbOrNull(v.quota) } }); FD.toast('Shared folder created. Now choose who can use it.'); loadSpaces(); }
    catch (e) { fail(e); }
};

async function editSpace(s) {
    const v = await FD.dialog({
        title: `Edit "${s.name}"`, ok: 'Save',
        fields: [
            { name: 'name', label: 'Name', value: s.name },
            { name: 'quota', label: 'Storage limit in GB (blank = no limit)', type: 'number', value: s.quota_bytes == null ? '' : +(s.quota_bytes / GB).toFixed(2), attrs: 'min="0" step="0.5"' },
        ],
    });
    if (!v) return;
    try { await api(`/spaces/${s.id}`, { method: 'PATCH', json: { name: v.name, quota_bytes: gbOrNull(v.quota), set_quota: true } }); FD.toast('Saved'); loadSpaces(); }
    catch (e) { fail(e); }
}

async function deleteSpace(s) {
    const v = await FD.dialog({
        title: `Delete "${s.name}"?`, ok: 'Delete for good', danger: true,
        body: `All ${FD.fmtSize(s.used_bytes)} of files in it are deleted for everyone. Type <b>${FD.esc(s.name)}</b> to confirm.`,
        fields: [{ name: 'confirm', label: 'Folder name', placeholder: s.name }],
    });
    if (!v) return;
    try { await api(`/spaces/${s.id}/delete`, { json: { confirm: v.confirm } }); FD.toast('Shared folder deleted'); loadSpaces(); }
    catch (e) { fail(e); }
}

// ---------- browse any space

let browse = { spaceId: null, folderId: 'root', data: null };

async function loadBrowser() {
    let data;
    try { data = await api('/spaces'); } catch (e) { return fail(e); }
    const opts = data.spaces.map(s => ({ id: s.id, label: s.kind === 'shared' ? `Shared: ${s.name}` : `${s.owner_display} (@${s.owner_username})` }));
    $('#spacePick').innerHTML = opts.map(o => `<option value="${o.id}">${FD.esc(o.label)}</option>`).join('');
    if (!opts.length) { $('#fileList').innerHTML = ''; $('#fileEmpty').hidden = false; $('#fileEmpty').textContent = 'No users or shared folders yet.'; return; }
    if (!opts.some(o => o.id === browse.spaceId)) browse = { spaceId: opts[0].id, folderId: 'root' };
    $('#spacePick').value = browse.spaceId;
    openBrowse(browse.spaceId, browse.folderId);
}

$('#spacePick').onchange = () => openBrowse($('#spacePick').value, 'root');

// Thumbnails on or off, remembered in this window (shared with the phone page's setting on this PC).
function renderAdminPreviews() {
    $('#adminPreviewsText').textContent = `Previews: ${FD.previewsOn() ? 'on' : 'off'}`;
    $('#adminPreviews').setAttribute('aria-pressed', String(FD.previewsOn()));
}
renderAdminPreviews();
$('#adminPreviews').onclick = () => {
    FD.setPreviews(!FD.previewsOn());
    renderAdminPreviews();
    if (browse.spaceId) openBrowse(browse.spaceId, browse.folderId);
};

function adminViewer(it) {
    FD.viewer({ name: it.name, kind: FD.viewable(it.name), src: `/api/download/${it.id}?inline=1`, download: `/api/download/${it.id}` });
}
$('#adminRefresh').onclick = () => openBrowse(browse.spaceId, browse.folderId);

async function openBrowse(spaceId, folderId) {
    let d;
    try { d = await api(`/spaces/${spaceId}/items?folder=${encodeURIComponent(folderId)}`); }
    catch (e) { if (folderId !== 'root') return openBrowse(spaceId, 'root'); return fail(e); }
    browse = { spaceId, folderId: d.folder_id, data: d };
    const label = $('#spacePick').selectedOptions[0]?.textContent || d.space.name;
    $('#crumbs').innerHTML = d.crumbs.map((c, i) =>
        `${i ? FD.icon('chevron', 'sep') : ''}<button type="button" data-id="${c.id}">${i ? FD.esc(c.name) : FD.icon('home') + '<span>' + FD.esc(label) + '</span>'}</button>`).join('');
    $('#crumbs').querySelectorAll('button').forEach(b => b.onclick = () => openBrowse(spaceId, b.dataset.id));
    $('#fileEmpty').hidden = d.items.length > 0;
    $('#fileEmpty').textContent = 'This folder is empty.';
    $('#fileList').innerHTML = d.items.map(it => {
        const isFolder = it.kind === 'folder', kind = isFolder ? 'folder' : FD.kindOf(it.name);
        const sub = isFolder ? `${it.child_count} items · ${FD.esc(it.created_by_name)}` : `${FD.fmtSize(it.size)} · ${FD.fmtDate(it.created_at)} · ${FD.esc(it.created_by_name)}`;
        const kindIcon = FD.icon(kind, `kind ${kind}`);
        const lead = FD.thumb(kindIcon, !isFolder && FD.previewsOn() && FD.hasThumb(it.name) ? `/api/thumb/${it.id}` : null);
        const name = !isFolder && FD.viewable(it.name)
            ? `<a class="name" href="/api/download/${it.id}?inline=1" data-act="view">${FD.esc(it.name)}</a>`
            : `<span class="name">${FD.esc(it.name)}</span>`;
        return `<li class="item ${isFolder ? 'folder' : ''}" data-id="${it.id}">${lead}
            <div class="meta">${name}<span class="sub">${sub}</span></div>
            <div class="row-actions">
                ${isFolder ? '' : `<a class="btn ghost small icon-only" href="/api/download/${it.id}" download title="Download">${FD.icon('download')}</a>`}
                <button class="btn ghost small icon-only" data-act="rename" title="Rename">${FD.icon('edit')}</button>
                <button class="btn ghost small icon-only danger" data-act="delete" title="Delete">${FD.icon('trash')}</button>
                ${isFolder ? FD.icon('chevron', 'go') : ''}
            </div></li>`;
    }).join('');
    FD.wireThumbs($('#fileList'));
    $('#fileList').querySelectorAll('.item').forEach(li => {
        const it = d.items.find(x => x.id === li.dataset.id);
        li.onclick = e => {
            if (e.target.closest('a, button')) return;
            if (it.kind === 'folder') openBrowse(spaceId, it.id);
            else if (FD.viewable(it.name)) adminViewer(it);
        };
        li.querySelector('[data-act=view]')?.addEventListener('click', e => { e.preventDefault(); adminViewer(it); });
        li.querySelector('[data-act=rename]').onclick = async () => {
            const v = await FD.dialog({ title: 'Rename', ok: 'Rename', fields: [{ name: 'name', label: 'New name', value: it.name }] });
            if (!v || !v.name.trim()) return;
            try { await api(`/items/${it.id}`, { method: 'PATCH', json: { name: v.name } }); openBrowse(spaceId, browse.folderId); } catch (e) { fail(e); }
        };
        li.querySelector('[data-act=delete]').onclick = async () => {
            if (!await FD.confirmBox(`Delete "${it.name}" for good?`, `This skips the trash. ${it.kind === 'folder' ? 'Everything inside the folder is deleted too.' : ''} The owner can't get it back.`)) return;
            try { await api(`/items/${it.id}/delete`, { json: {} }); FD.toast('Deleted'); openBrowse(spaceId, browse.folderId); } catch (e) { fail(e); }
        };
    });
}

$('#adminNewFolder').onclick = async () => {
    const v = await FD.dialog({ title: 'New folder', ok: 'Create', fields: [{ name: 'name', label: 'Folder name' }] });
    if (!v || !v.name.trim()) return;
    try { await api(`/spaces/${browse.spaceId}/folders`, { json: { parent_id: browse.folderId, name: v.name } }); openBrowse(browse.spaceId, browse.folderId); }
    catch (e) { fail(e); }
};

// ---------- activity

const ACTIONS = {
    login: 'Signed in', 'password.change': 'Changed password', 'server.start': 'Started web server', 'server.stop': 'Stopped web server',
    'uploads.pause': 'Paused uploads', 'uploads.resume': 'Allowed uploads', 'downloads.pause': 'Paused downloads', 'downloads.resume': 'Allowed downloads',
    'user.create': 'Created user', 'user.edit': 'Edited user', 'user.password_reset': 'Reset password for', 'user.delete': 'Deleted user',
    'session.revoke': 'Signed out a device', 'upload.cancel': 'Cancelled upload', 'space.create': 'Created shared folder',
    'space.edit': 'Edited shared folder', 'space.delete': 'Deleted shared folder', 'space.access': 'Changed shared folder access for',
    'item.rename': 'Renamed', 'item.delete': 'Deleted', 'storage.setup': 'Chose storage folder', 'storage.move': 'Moved storage to', 'admin.unlock': 'Wrong admin PIN', 'admin.pin_set': 'Set the admin PIN', 'admin.pin_removed': 'Removed the admin PIN', 'server.https_on': 'Turned on HTTPS', 'server.https_off': 'Turned off HTTPS',
};

async function loadActivity() {
    let data;
    try { data = await api('/audit?limit=200'); } catch (e) { return fail(e); }
    $('#logEmpty').hidden = data.entries.length > 0;
    $('#log').innerHTML = data.entries.map(a => {
        let label = ACTIONS[a.action] || a.action;
        if (a.action === 'login' && a.result !== 'ok') label = a.details.locked ? 'Wrong password (locked out)' : 'Failed sign-in';
        const target = a.target_name ? ` <b>${FD.esc(a.target_name)}</b>` : '';
        const extra = a.action === 'space.access' ? ` → ${FD.esc(a.details.level || 'no access')}` : '';
        return `<li><time title="${new Date(a.at).toLocaleString()}">${FD.fmtAgo(a.at)}</time>
            <span class="who">${FD.esc(a.actor_name)}</span>
            <span class="detail">${label}${target}${extra}</span>
            ${a.result === 'ok' ? '' : `<span class="badge bad">${FD.esc(a.result)}</span>`}</li>`;
    }).join('');
}
$('#activityRefresh').onclick = loadActivity;

// ---------- backups (Pro)

let backupTimer = null;

async function loadBackups() {
    let b;
    try { b = await api('/backup'); } catch (e) { return fail(e); }
    $('#backupProNote').hidden = b.pro;
    ['#backupEnabled', '#backupFolder', '#backupEvery', '#backupKeep', '#backupSave', '#backupBrowse']
        .forEach(id => { $(id).disabled = !b.pro; });
    $('#backupBrowse').hidden = !b.can_browse;
    if (!document.activeElement || !document.activeElement.closest('[data-view=backups]')) {
        $('#backupEnabled').checked = b.config.enabled;
        $('#backupFolder').value = b.config.folder;
        $('#backupEvery').value = String(b.config.every_hours);
        $('#backupKeep').value = b.config.keep;
    }
    $('#backupRun').disabled = !b.pro || b.running || !b.config.folder;
    pageRestore.setFolder(b.config.folder);
    const s = b.state;
    $('#backupLast').innerHTML = b.running ? '<b>Backing up now…</b> You can keep using WiFiDrop.'
        : !s.last_at ? 'No backup yet.'
        : s.ok ? `<span class="badge ok">OK</span> ${FD.fmtAgo(s.last_at)}: ${s.files} file(s), ${s.copied} new (${FD.fmtSize(s.copied_bytes || 0)}), took ${s.seconds}s.<br><span class="muted">${FD.esc(s.folder || '')}</span>`
        : `<span class="badge bad">Failed</span> ${FD.fmtAgo(s.last_at)}: ${FD.esc(s.error)} WiFiDrop tries again every hour.`;
    clearTimeout(backupTimer);
    if (b.running && page === 'backups') backupTimer = setTimeout(loadBackups, 2000);
}

$('#backupBrowse').onclick = async () => {
    try { const r = await api('/storage/choose', { json: {} }); if (r.path) $('#backupFolder').value = r.path; } catch (e) { fail(e); }
};
$('#backupSave').onclick = async () => {
    try {
        await api('/backup', { method: 'PUT', json: { enabled: $('#backupEnabled').checked, folder: $('#backupFolder').value,
            every_hours: Number($('#backupEvery').value), keep: Number($('#backupKeep').value) } });
        FD.toast('Backup settings saved');
        $('#backupSave').blur();
        loadBackups();
    } catch (e) { fail(e); }
};
$('#backupRun').onclick = async () => {
    try { await api('/backup/run', { json: {} }); FD.toast('Backup started'); loadBackups(); } catch (e) { fail(e); }
};

// ---------- restore from a backup (Backups page, and the first-run setup screen on a new PC)

function restorePanel(prefix, { storagePath = null, done }) {
    const show = msg => { $(`#${prefix}Error`).textContent = msg; $(`#${prefix}Error`).hidden = !msg; };
    let folder = '';

    async function find() {
        show('');
        $(`#${prefix}Tbl`).innerHTML = '';
        try {
            const r = await api('/backup/inspect', { json: { folder: $(`#${prefix}Folder`).value } });
            folder = r.folder;
            if (!r.snapshots.length) return show('That backup has no copies that can be restored.');
            $(`#${prefix}Tbl`).innerHTML = '<tr><th>Backup from</th><th>Accounts</th><th>Files</th><th></th></tr>' + r.snapshots.map((s, i) => `
                <tr><td><div class="strong">${FD.fmtDate(s.created_at)}</div><div class="muted small">${FD.fmtAgo(s.created_at)}</div></td>
                <td>${s.users}</td><td class="small">${s.files} (${FD.fmtSize(s.bytes)})</td>
                <td class="actions">${s.newer ? '<span class="badge warn">needs newer WiFiDrop</span>'
                    : `<button class="btn ${i ? 'ghost' : 'primary'} small" type="button" data-restore="${FD.esc(s.name)}">Restore</button>`}</td></tr>`).join('');
            $(`#${prefix}Tbl`).querySelectorAll('[data-restore]').forEach(b => b.onclick = () => restoreCopy(b.dataset.restore, b));
        } catch (e) { show(e.message); }
    }

    async function restoreCopy(name, button) {
        const row = button.closest('tr').querySelector('.strong').textContent;
        if (!await FD.confirmBox(`Restore the backup from ${row}?`,
            'Accounts, folders and files go back to how they were then. Anything added since won\'t show any more. Everyone signs in again. If the backup had an admin PIN, it comes back too. Your current state is saved first, so this can be undone.',
            'Restore')) return;
        button.disabled = true;
        button.textContent = 'Restoring…';
        try {
            const body = { folder, name };
            if (storagePath) body.storage_path = storagePath();
            const r = await api('/backup/restore', { json: body });
            FD.toast(`Restored: ${r.users} account(s) and ${r.files} file(s)${r.missing ? `, ${r.missing} file(s) missing from the backup` : ''}.`);
            done(r);
        } catch (e) {
            show(e.message);
            button.disabled = false;
            button.textContent = 'Restore';
        }
    }

    $(`#${prefix}Find`).onclick = find;
    $(`#${prefix}Folder`).addEventListener('keydown', e => { if (e.key === 'Enter') find(); });
    $(`#${prefix}Browse`).onclick = async () => {
        try { const r = await api('/storage/choose', { json: {} }); if (r.path) { $(`#${prefix}Folder`).value = r.path; find(); } }
        catch (e) { show(e.message); }
    };
    return { find, setFolder: f => { if (f && !$(`#${prefix}Folder`).value) $(`#${prefix}Folder`).value = f; } };
}

const pageRestore = restorePanel('restore', { done: () => { refreshPin(); go('dashboard'); } });
const setupRestore = restorePanel('setupRestore', {
    storagePath: () => $('#setupPath').value,
    done: () => { $('#setup').hidden = true; refreshPin(); go('dashboard'); },
});
$('#setupRestoreToggle').onclick = () => { $('#setupRestore').hidden = !$('#setupRestore').hidden; };

// ---------- licence

const LIC_STATE = {
    free: ['WiFiDrop Free', '', 'Free includes up to 5 accounts and everything you need to share files at home.'],
    pro: ['WiFiDrop Pro', 'ok', 'Thank you for supporting WiFiDrop! Pro is active on this PC.'],
    revoked: ['WiFiDrop Pro (cancelled)', 'bad', ''],
    limit: ['WiFiDrop Pro (too many PCs)', 'warn', ''],
    updates_ended: ['WiFiDrop Pro (updates ended)', 'warn', ''],
    invalid: ['WiFiDrop Free', 'bad', ''],
};

function renderLicence(e) {
    renderEdition(e, overview && overview.website_url);
    const [title, badge, text] = LIC_STATE[e.state] || LIC_STATE.free;
    $('#licTitle').textContent = title;
    $('#licBadge').textContent = e.pro ? 'PRO' : 'FREE';
    $('#licBadge').className = `badge ${badge}`;
    $('#licText').textContent = text;
    $('#licProblem').hidden = !e.message;
    $('#licProblemText').textContent = e.message || '';
    $('#freeLimitCell').textContent = e.free_max_users;
    const has = !!e.licence_id;
    $('#licActions').hidden = !has;
    $('#licPasteCard').hidden = has;
    $('#licMeta').hidden = !has;
    if (has) {
        const rows = [['Licence', e.licence_id], ['Licensed to', e.licensee], ['Updates until', e.updates_until],
            ['This PC', e.activated ? 'Activated' : 'Not confirmed yet (WiFiDrop will try again when online)'],
            ['Use on up to', e.max_activations ? `${e.max_activations} PCs` : '']].filter(([, v]) => v);
        $('#licMeta').innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${FD.esc(v)}</dd>`).join('');
    }
}

async function loadLicence() {
    try { if (!overview) overview = await api('/overview'); renderLicence(await api('/licence')); } catch (e) { fail(e); }
}

$('#licSave').onclick = async () => {
    const text = $('#licInput').value.trim();
    if (!text) return FD.toast('Paste your licence first', 'err');
    $('#licSave').disabled = true;
    try {
        const r = await api('/licence', { json: { licence: text } });
        $('#licInput').value = '';
        renderLicence(r);
        FD.toast(r.pro ? (r.online ? 'WiFiDrop Pro is active' : 'Pro is on. WiFiDrop will confirm it when online.')
            : (r.message || r.notice || 'Licence saved'), r.pro ? 'ok' : 'err');
    } catch (e) { fail(e); } finally { $('#licSave').disabled = false; }
};
$('#licCheck').onclick = async () => {
    try {
        const r = await api('/licence/check', { json: {} });
        renderLicence(r);
        FD.toast(r.online ? 'Licence checked' : r.notice, r.online ? 'ok' : 'err');
    } catch (e) { fail(e); }
};
$('#licRemove').onclick = async () => {
    if (!await FD.confirmBox('Remove the licence from this PC?', 'WiFiDrop goes back to Free and frees this PC so you can use the licence on another one. Your files and accounts stay. Keep your licence email to add it again.', 'Remove licence')) return;
    try { const r = await api('/licence/remove', { json: {} }); renderLicence(r); FD.toast('Licence removed'); } catch (e) { fail(e); }
};

// ---------- about and open-source licences

async function loadAbout() {
    try {
        const o = overview || await api('/overview');
        $('#aboutVersion').textContent = `v${o.version}`;
        $('#aboutBuilt').textContent = `Released ${o.build_date}.`;
        $('#aboutEdition').textContent = o.edition && o.edition.pro ? 'PRO' : 'FREE';
        $('#aboutEdition').className = `badge ${o.edition && o.edition.pro ? 'accent' : ''}`;
        if (o.website_url) {
            $('#aboutWebsite').href = o.website_url; $('#aboutWebsite').hidden = false;
            $('#aboutPrivacy').href = `${o.website_url}/privacy.html`; $('#aboutPrivacy').hidden = false;
        }
        if (!$('#ossTbl').rows.length) {
            const list = await (await fetch('/licences.json')).json();
            $('#ossTbl').innerHTML = '<tr><th>Component</th><th>Version</th><th>Licence</th></tr>' + list.map(c =>
                `<tr><td>${c.url ? `<a href="${FD.esc(c.url)}" target="_blank" rel="noopener">${FD.esc(c.name)}</a>` : FD.esc(c.name)}</td>
                 <td class="muted small">${FD.esc(c.version)}</td><td class="small">${FD.esc(c.license)}</td></tr>`).join('');
        }
    } catch (e) { fail(e); }
}

// ---------- admin PIN

let pinSet = false;

function showLock() {
    if (!$('#lockScreen').hidden) return;
    $('#lockScreen').hidden = false;
    $('#lockError').hidden = true;
    $('#lockPin').value = '';
    $('#lockPin').focus();
}

$('#lockForm').addEventListener('submit', async e => {
    e.preventDefault();
    try {
        await FD.api('/api/unlock', { json: { pin: $('#lockPin').value } });
        $('#lockScreen').hidden = true;
        go(page);
    } catch (ex) {
        $('#lockError').textContent = ex.message;
        $('#lockError').hidden = false;
        $('#lockPin').select();
    }
});

async function refreshPin() {
    const s = await FD.api('/api/lock');
    pinSet = s.pin_set;
    $('#pinText').textContent = pinSet
        ? 'A PIN is needed to open this window. It locks again when you close the window or after 30 idle minutes.'
        : 'Anyone using this PC can open this window. Set a PIN to stop others managing users and files.';
    $('#pinSetText').textContent = pinSet ? 'Change PIN' : 'Set a PIN';
    $('#pinRemove').hidden = !pinSet;
    $('#lockNowBtn').hidden = !pinSet;
    return s;
}

$('#pinSet').onclick = async () => {
    const v = await FD.dialog({
        title: pinSet ? 'Change admin PIN' : 'Set an admin PIN', ok: 'Save PIN',
        body: 'Use 4 or more characters. WiFiDrop keeps serving files while this window is locked.',
        fields: [{ name: 'pin', label: 'New PIN', type: 'password' }, { name: 'pin2', label: 'New PIN again', type: 'password' }],
    });
    if (!v) return;
    if (v.pin !== v.pin2) return FD.toast("The PINs don't match", 'err');
    try { await api('/lock/set', { json: { pin: v.pin } }); FD.toast('Admin PIN saved'); refreshPin(); } catch (e) { fail(e); }
};

$('#pinRemove').onclick = async () => {
    if (!await FD.confirmBox('Remove the admin PIN?', 'Anyone using this PC will be able to open this window.', 'Remove PIN')) return;
    try { await api('/lock/remove', { json: {} }); FD.toast('Admin PIN removed'); refreshPin(); } catch (e) { fail(e); }
};

$('#lockNowBtn').onclick = async () => {
    try { await api('/lock/now', { json: {} }); } catch { /* locked anyway */ }
    showLock();
};

FD.hydrate();
const startPage = location.hash.slice(1) || 'dashboard';
refreshPin().then(s => { if (s.pin_set && !s.unlocked) { page = startPage; showLock(); } else go(startPage); }).catch(() => go(startPage));
