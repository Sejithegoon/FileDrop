// Admin window: server controls, users, shared folders, file browser, activity.
const $ = s => document.querySelector(s);
const GB = 1024 ** 3;
let page = 'dashboard';
let overview = null;

const api = (url, opts) => FD.api('/api' + url, opts);
const fail = e => FD.toast(e.message, 'err');
const gbOrNull = v => (v === '' || v == null ? null : Math.round(parseFloat(v) * GB));
const quotaText = (used, quota) => quota == null ? `${FD.fmtSize(used)} · no limit` : `${FD.fmtSize(used)} of ${FD.fmtSize(quota)}`;

// ---------- navigation

function go(p) {
    page = p;
    document.querySelectorAll('#nav button').forEach(b => b.toggleAttribute('aria-current', b.dataset.page === p));
    document.querySelectorAll('[data-view]').forEach(v => { v.hidden = v.dataset.view !== p; });
    ({ dashboard: loadDashboard, users: loadUsers, shared: loadSpaces, files: loadBrowser, activity: loadActivity })[p]();
}
document.querySelectorAll('#nav button').forEach(b => b.onclick = () => go(b.dataset.page));

// ---------- dashboard

async function loadDashboard() {
    try { overview = await api('/overview'); } catch (e) { return markOffline(); }
    const o = overview, running = o.server.state === 'running';
    $('#version').textContent = `v${o.version}`;
    $('#serverState').classList.toggle('running', running);
    $('#serverText').textContent = running ? 'Web server is running' : o.server.state === 'starting' ? 'Starting…' : 'Web server is stopped';
    $('#serverHint').textContent = running
        ? 'People on the same Wi-Fi can open this link or scan the code, then sign in with their account.'
        : 'Nobody can connect while the web server is stopped. Your files are safe.';
    $('#serverUrl').textContent = o.url;
    $('#qr').innerHTML = o.qr;
    $('#qr').classList.toggle('off', !running);
    $('#serverBtnText').textContent = running ? 'Stop web server' : 'Start web server';
    $('#serverBtn').className = running ? 'btn danger' : 'btn primary';
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
    $('#sidePill').className = `pill ${running ? '' : 'bad'}`;
    $('#sideState').textContent = running ? 'Server running' : 'Server stopped';
    loadSessions();
}

function markOffline() {
    $('#sidePill').className = 'pill bad';
    $('#sideState').textContent = 'FileDrop not responding';
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
                (c.existing_store ? ' · existing FileDrop folder' : c.exists ? '' : ' · will be created');
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

$('#quitBtn').onclick = async () => {
    if (!await FD.confirmBox('Quit FileDrop?', 'The web server stops for everyone until you open FileDrop again.', 'Quit')) return;
    try { await api('/quit', { json: {} }); } catch { /* window closes */ }
};

// ---------- users

async function loadUsers() {
    let data;
    try { data = await api('/users'); } catch (e) { return fail(e); }
    $('#usersEmpty').hidden = data.users.length > 0;
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
        return `<li class="item ${isFolder ? 'folder' : ''}" data-id="${it.id}">${FD.icon(kind, `kind ${kind}`)}
            <div class="meta"><span class="name">${FD.esc(it.name)}</span><span class="sub">${sub}</span></div>
            <div class="row-actions">
                ${isFolder ? '' : `<a class="btn ghost small icon-only" href="/api/download/${it.id}" download title="Download">${FD.icon('download')}</a>`}
                <button class="btn ghost small icon-only" data-act="rename" title="Rename">${FD.icon('edit')}</button>
                <button class="btn ghost small icon-only danger" data-act="delete" title="Delete">${FD.icon('trash')}</button>
                ${isFolder ? FD.icon('chevron', 'go') : ''}
            </div></li>`;
    }).join('');
    $('#fileList').querySelectorAll('.item').forEach(li => {
        const it = d.items.find(x => x.id === li.dataset.id);
        li.onclick = e => { if (!e.target.closest('a, button') && it.kind === 'folder') openBrowse(spaceId, it.id); };
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
    'item.rename': 'Renamed', 'item.delete': 'Deleted', 'storage.setup': 'Chose storage folder', 'storage.move': 'Moved storage to',
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

FD.hydrate();
go('dashboard');
