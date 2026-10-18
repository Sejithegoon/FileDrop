// User page: sign in, browse spaces and folders, upload (chunked, resumable, parallel), download.
const $ = s => document.querySelector(s);
const API = '/api/v1';
const MAX_PARALLEL = 3;

let me = null;
let spaces = [];
let cur = { spaceId: null, folderId: 'root' };
let view = null;      // last folder listing
let trashOpen = false;

// ---------- screens

function show(which) {
    $('#loginView').hidden = which !== 'login';
    $('#pwView').hidden = which !== 'pw';
    $('#appView').hidden = which !== 'app';
    document.body.classList.toggle('centered', which !== 'app');
}

async function call(url, opts) {
    try {
        return await FD.api(API + url, opts);
    } catch (e) {
        if (e.status === 401) { signedOut(); }
        else if (e.code === 'PASSWORD_CHANGE_REQUIRED') { show('pw'); }
        throw e;
    }
}

function signedOut() {
    me = null;
    jobs.forEach(j => { if (j.status === 'uploading' || j.status === 'queued') cancelJob(j, true); });
    show('login');
}

async function boot() {
    FD.hydrate();
    try {
        me = await FD.api(API + '/me');
    } catch {
        show('login');
        $('#loginUser').focus();
        return;
    }
    enter();
}

async function enter() {
    if (me.user.must_change_password) { show('pw'); $('#pwCurrent').focus(); return; }
    show('app');
    $('#userName').textContent = me.user.display_name;
    $('#menuName').textContent = me.user.display_name;
    $('#menuUser').textContent = `@${me.user.username}${me.user.role === 'admin' ? ' · admin' : ''}`;
    renderPause();
    await loadSpaces();
    const [sid, fid] = location.hash.replace(/^#\/?/, '').split('/');
    const start = spaces.find(s => s.id === sid) || spaces[0];
    if (start) await openFolder(start.id, (sid === start.id && fid) || 'root', false);
}

$('#loginForm').addEventListener('submit', async e => {
    e.preventDefault();
    const err = $('#loginError');
    err.hidden = true;
    try {
        me = await FD.api(API + '/auth/login', { json: { username: $('#loginUser').value, password: $('#loginPass').value } });
        $('#loginPass').value = '';
        enter();
    } catch (ex) {
        err.textContent = ex.message;
        err.hidden = false;
    }
});

$('#pwForm').addEventListener('submit', async e => {
    e.preventDefault();
    const err = $('#pwError');
    err.hidden = true;
    if ($('#pwNew').value !== $('#pwNew2').value) { err.textContent = "The new passwords don't match."; err.hidden = false; return; }
    try {
        me = await FD.api(API + '/me/password', { json: { current: $('#pwCurrent').value, new: $('#pwNew').value } });
        ['#pwCurrent', '#pwNew', '#pwNew2'].forEach(s => { $(s).value = ''; });
        FD.toast('Password saved');
        enter();
    } catch (ex) {
        if (ex.status === 401) { show('login'); return; }
        err.textContent = ex.message;
        err.hidden = false;
    }
});

// ---------- user menu

$('#userBtn').onclick = e => { e.stopPropagation(); $('#userMenu').hidden = !$('#userMenu').hidden; };
document.addEventListener('click', () => { $('#userMenu').hidden = true; });
$('#logoutBtn').onclick = async () => {
    try { await FD.api(API + '/auth/logout', { json: {} }); } catch { /* signed out anyway */ }
    signedOut();
};
$('#changePwBtn').onclick = async () => {
    const v = await FD.dialog({
        title: 'Change password', ok: 'Save',
        fields: [
            { name: 'current', label: 'Current password', type: 'password' },
            { name: 'new', label: 'New password (8+ characters)', type: 'password' },
            { name: 'new2', label: 'New password again', type: 'password' },
        ],
    });
    if (!v) return;
    if (v.new !== v.new2) return FD.toast("The new passwords don't match", 'err');
    try { me = await call('/me/password', { json: { current: v.current, new: v.new } }); FD.toast('Password changed. Other devices were signed out.'); }
    catch (e) { FD.toast(e.message, 'err'); }
};

// ---------- pause banner

function renderPause() {
    const s = me.status, parts = [];
    if (s.uploads_paused) parts.push('Uploads');
    if (s.downloads_paused) parts.push('Downloads');
    $('#pauseNote').hidden = !parts.length;
    $('#pauseText').textContent = `${parts.join(' and ').replace(' and D', ' and d')} are paused by the administrator.`;
    renderDrop();
}

// ---------- live updates: when anyone changes something, reload what's on screen.
// A tiny request every few seconds while the page is visible; it also notices sign-outs.

let seenVersion = null;
let liveBusy = false;

async function checkForChanges() {
    if (!me || document.hidden || liveBusy) return;
    liveBusy = true;
    try {
        const { version } = await call('/changes');
        if (seenVersion !== null && version !== seenVersion) {
            me = await call('/me');
            renderPause();
            await loadSpaces();
            await refresh();
        }
        seenVersion = version;
    } catch { /* offline for a moment, or signed out (handled in call()) */ }
    finally { liveBusy = false; }
}
setInterval(checkForChanges, 3000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) checkForChanges(); });

// Downloads: check the file still exists first, so a file someone just deleted gives a clear
// message (and a fresh list) instead of a broken download.
document.addEventListener('click', async e => {
    const a = e.target.closest('#list a[download]');
    if (!a || e.ctrlKey || e.metaKey) return;
    e.preventDefault();
    try {
        const r = await fetch(a.href, { headers: { Range: 'bytes=0-0' }, credentials: 'same-origin' });
        if (r.ok) {
            const go = Object.assign(document.createElement('a'), { href: a.href, download: '' });
            document.body.appendChild(go); go.click(); go.remove();
            return;
        }
        const data = await r.json().catch(() => ({}));
        FD.toast(r.status === 404 ? 'That file was deleted or moved. The list has been refreshed.'
            : (data.error && data.error.message) || "Couldn't download that file.", 'err');
        refresh();
    } catch {
        FD.toast("Can't reach the server. Is WiFiDrop still running?", 'err');
    }
});

// ---------- spaces and folders

async function loadSpaces() {
    spaces = (await call('/spaces')).spaces;
    renderTabs();
}

function renderTabs() {
    $('#tabs').innerHTML = spaces.map(s => `
        <button class="tab" role="tab" data-id="${s.id}" aria-selected="${s.id === cur.spaceId}">
            ${FD.icon(s.kind === 'private' ? 'home' : 'share')} ${FD.esc(s.kind === 'private' ? 'My files' : s.name)}
            ${s.kind === 'shared' && s.level === 'view' ? '<span class="badge">view</span>' : ''}
        </button>`).join('');
    $('#tabs').querySelectorAll('.tab').forEach(b => b.onclick = () => openFolder(b.dataset.id, 'root'));
}

async function openFolder(spaceId, folderId = 'root', push = true) {
    try {
        view = await call(`/spaces/${spaceId}/items?folder=${encodeURIComponent(folderId)}`);
    } catch (e) {
        if (e.status === 404 && folderId !== 'root') return openFolder(spaceId, 'root', push);
        if (e.status === 404) { await loadSpaces(); if (spaces[0] && spaces[0].id !== spaceId) return openFolder(spaces[0].id); }
        return FD.toast(e.message, 'err');
    }
    cur = { spaceId, folderId: view.folder_id };
    const hash = `#/${spaceId}/${view.folder_id}`;
    if (push && location.hash !== hash) history.pushState(null, '', hash);
    else history.replaceState(null, '', hash);
    renderTabs();
    renderCrumbs();
    renderList();
    renderDrop();
    if (trashOpen) loadTrash();
}

window.addEventListener('popstate', () => {
    const [sid, fid] = location.hash.replace(/^#\/?/, '').split('/');
    if (sid && me) openFolder(sid, fid || 'root', false);
});

const refresh = () => cur.spaceId && openFolder(cur.spaceId, cur.folderId, false);
$('#refreshBtn').onclick = refresh;

function spaceLabel() {
    return view.space.kind === 'private' ? 'My files' : view.space.name;
}

function renderCrumbs() {
    const el = $('#crumbs');
    el.innerHTML = view.crumbs.map((c, i) => {
        const label = i === 0 ? `${FD.icon(view.space.kind === 'private' ? 'home' : 'share')}<span>${FD.esc(spaceLabel())}</span>` : FD.esc(c.name);
        return `${i ? FD.icon('chevron', 'sep') : ''}<button type="button" data-id="${c.id}">${label}</button>`;
    }).join('');
    el.querySelectorAll('button').forEach(b => b.onclick = () => openFolder(cur.spaceId, b.dataset.id));
    el.lastElementChild?.setAttribute('aria-current', 'page');
}

function renderDrop() {
    if (!view || !me) return;
    const paused = me.status.uploads_paused;
    const can = view.can_upload && !paused;
    $('#drop').classList.toggle('disabled', !can);
    $('#pickBtn').disabled = !can;
    $('#viewOnlyNote').hidden = view.can_upload;
    $('#newFolderBtn').hidden = !view.can_upload;
    const last = view.crumbs[view.crumbs.length - 1];
    $('#destName').textContent = view.crumbs.length > 1 ? `${spaceLabel()} / ${last.name}` : spaceLabel();
    const q = view.space.quota_bytes;
    $('#quota').hidden = q == null;
    if (q != null) {
        const pct = Math.min(100, (view.space.used_bytes / Math.max(q, 1)) * 100);
        $('#quotaText').textContent = `${FD.fmtSize(view.space.used_bytes)} of ${FD.fmtSize(q)} used`;
        $('#quotaBar').style.width = pct + '%';
        $('#quota').classList.toggle('full', pct >= 90);
    }
}

function itemRow(it) {
    const isFolder = it.kind === 'folder';
    const kind = isFolder ? 'folder' : FD.kindOf(it.name);
    const by = view.space.kind === 'shared' ? ` · ${FD.esc(it.created_by_name)}` : '';
    const sub = isFolder
        ? `${it.child_count} item${it.child_count === 1 ? '' : 's'} · ${FD.fmtDate(it.created_at)}${by}`
        : `${FD.fmtSize(it.size)} · ${FD.fmtDate(it.created_at)}${by}`;
    const dl = `${API}/download/${it.id}`;
    const nameEl = isFolder
        ? `<span class="name">${FD.esc(it.name)}</span>`
        : `<a class="name" href="${dl}" download>${FD.esc(it.name)}</a>`;
    return `<li class="item ${isFolder ? 'folder' : ''}" data-id="${it.id}">
        ${FD.icon(kind, `kind ${kind}`)}
        <div class="meta">${nameEl}<span class="sub">${sub}</span></div>
        <div class="row-actions">
            ${!isFolder ? `<a class="btn ghost small icon-only" href="${dl}" download aria-label="Download" title="Download">${FD.icon('download')}</a>` : ''}
            ${it.can_modify ? `<button class="btn ghost small icon-only" data-act="more" aria-label="More actions" title="Move, rename or delete">${FD.icon('more')}</button>` : ''}
            ${isFolder ? FD.icon('chevron', 'go') : ''}
        </div></li>`;
}

function renderList() {
    $('#list').innerHTML = view.items.map(itemRow).join('');
    $('#empty').hidden = view.items.length > 0;
    $('#empty').textContent = view.can_upload
        ? (view.crumbs.length > 1 ? 'This folder is empty. Upload files into it.' : 'Nothing here yet. Upload files, or make folders like "Pics" and "School".')
        : 'Nothing here yet.';
    $('#list').querySelectorAll('.item').forEach(li => {
        const it = view.items.find(x => x.id === li.dataset.id);
        li.onclick = e => {
            if (e.target.closest('a, button')) return;
            if (it.kind === 'folder') openFolder(cur.spaceId, it.id);
        };
        li.querySelector('[data-act=more]')?.addEventListener('click', () => itemMenu(it));
    });
}

$('#newFolderBtn').onclick = async () => {
    const where = view.crumbs.length > 1 ? ` inside "${view.crumbs[view.crumbs.length - 1].name}"` : '';
    const v = await FD.dialog({ title: `New folder${where}`, ok: 'Create', fields: [{ name: 'name', label: 'Folder name', placeholder: 'e.g. Pics or School' }] });
    if (!v || !v.name.trim()) return;
    try { await call(`/spaces/${cur.spaceId}/folders`, { json: { parent_id: cur.folderId, name: v.name } }); FD.toast(`Folder "${v.name.trim()}" created. Tap it to open.`); refresh(); }
    catch (e) { FD.toast(e.message, 'err'); }
};

async function itemMenu(it) {
    const actions = [
        { key: 'move', label: 'Move to folder', icon: 'move' },
        { key: 'rename', label: 'Rename', icon: 'edit' },
        { key: 'delete', label: 'Delete', icon: 'trash', danger: true },
    ];
    const pick = await FD.sheet(it.name, actions);
    if (pick === 'move') moveItem(it);
    else if (pick === 'rename') renameItem(it);
    else if (pick === 'delete') deleteItem(it);
}

async function moveItem(it) {
    let folders;
    try { folders = (await call(`/spaces/${cur.spaceId}/folders?exclude=${encodeURIComponent(it.id)}`)).folders; }
    catch (e) { return FD.toast(e.message, 'err'); }
    const options = folders.filter(f => f.id !== cur.folderId)
        .map(f => ({ value: f.id, label: f.is_root ? `${spaceLabel()} (top)` : `${spaceLabel()} / ${f.path.replaceAll('/', ' / ')}` }));
    if (!options.length) return FD.toast('Make a folder first, then move things into it.', 'err');
    const v = await FD.dialog({
        title: `Move "${it.name}"`, ok: 'Move',
        fields: [{ name: 'target', label: 'Move to', type: 'select', value: options[0].value, options }],
    });
    if (!v) return;
    try {
        const moved = await call(`/items/${it.id}`, { method: 'PATCH', json: { parent_id: v.target } });
        const dest = options.find(o => o.value === v.target).label;
        FD.toast(moved.name !== it.name ? `Moved to ${dest} as "${moved.name}"` : `Moved to ${dest}`);
        refresh();
    } catch (e) { FD.toast(e.message, 'err'); }
}

async function renameItem(it) {
    const v = await FD.dialog({ title: `Rename ${it.kind}`, ok: 'Rename', fields: [{ name: 'name', label: 'New name', value: it.name }] });
    if (!v || !v.name.trim() || v.name === it.name) return;
    try { await call(`/items/${it.id}`, { method: 'PATCH', json: { name: v.name } }); refresh(); }
    catch (e) { FD.toast(e.message, 'err'); }
}

async function deleteItem(it) {
    try {
        await call(`/items/${it.id}`, { method: 'DELETE' });
        FD.toast(`Moved "${it.name}" to Trash`);
        refresh();
    } catch (e) { FD.toast(e.message, 'err'); }
}

// ---------- trash

$('#trashBtn').onclick = () => { trashOpen = true; loadTrash(); $('#trashCard').scrollIntoView({ behavior: 'smooth' }); };
$('#closeTrashBtn').onclick = () => { trashOpen = false; $('#trashCard').hidden = true; };

async function loadTrash() {
    let data;
    try { data = await call(`/spaces/${cur.spaceId}/trash`); } catch (e) { return FD.toast(e.message, 'err'); }
    $('#trashCard').hidden = false;
    $('#emptyTrashBtn').hidden = !(['manage', 'owner'].includes(view.space.level) && data.items.length);
    $('#trashEmpty').hidden = data.items.length > 0;
    $('#trashList').innerHTML = data.items.map(it => {
        const kind = it.kind === 'folder' ? 'folder' : FD.kindOf(it.name);
        return `<li class="item" data-id="${it.id}">${FD.icon(kind, `kind ${kind}`)}
            <div class="meta"><span class="name">${FD.esc(it.name)}</span>
            <span class="sub">${it.kind === 'file' ? FD.fmtSize(it.size) + ' · ' : ''}deleted ${FD.fmtAgo(it.trashed_at)}</span></div>
            <div class="row-actions">
                <button class="btn ghost small" data-act="restore">${FD.icon('restore')} Restore</button>
                <button class="btn ghost small icon-only danger" data-act="purge" aria-label="Delete forever" title="Delete forever">${FD.icon('x')}</button>
            </div></li>`;
    }).join('');
    $('#trashList').querySelectorAll('.item').forEach(li => {
        const it = data.items.find(x => x.id === li.dataset.id);
        li.querySelector('[data-act=restore]').onclick = async () => {
            try { await call(`/items/${it.id}/restore`, { json: {} }); FD.toast(`Restored "${it.name}"`); refresh(); }
            catch (e) { FD.toast(e.message, 'err'); }
        };
        li.querySelector('[data-act=purge]').onclick = async () => {
            if (!await FD.confirmBox('Delete forever?', `"${FD.esc(it.name)}" will be gone for good.`)) return;
            try { await call(`/items/${it.id}/purge`, { method: 'DELETE' }); loadTrash(); refresh(); }
            catch (e) { FD.toast(e.message, 'err'); }
        };
    });
}

$('#emptyTrashBtn').onclick = async () => {
    if (!await FD.confirmBox('Empty trash?', 'Everything in this trash will be deleted for good.', 'Empty trash')) return;
    try { await call(`/spaces/${cur.spaceId}/trash`, { method: 'DELETE' }); loadTrash(); refresh(); }
    catch (e) { FD.toast(e.message, 'err'); }
};

// ---------- uploads

const jobs = [];
let jobSeq = 0;

if (/iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) {
    $('#iosHint').hidden = false;
}

$('#pickBtn').onclick = () => $('#picker').click();
$('#picker').onchange = () => { addFiles([...$('#picker').files]); $('#picker').value = ''; };

function addFiles(list) {
    if (!list.length) return;
    if (!view?.can_upload) return FD.toast("You can't upload to this folder", 'err');
    if (me.status.uploads_paused) return FD.toast('Uploads are paused by the administrator', 'err');
    const dest = $('#destName').textContent;
    for (const file of list) {
        jobs.push({ id: ++jobSeq, file, spaceId: cur.spaceId, folderId: cur.folderId, dest, status: 'queued', loaded: 0, error: '' });
    }
    $('#queueCard').hidden = false;
    pump();
    paintSoon();
}

function pump() {
    const running = jobs.filter(j => j.status === 'uploading').length;
    jobs.filter(j => j.status === 'queued').slice(0, MAX_PARALLEL - running).forEach(runJob);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function runJob(job) {
    job.status = 'uploading';
    job.started = Date.now();
    paintSoon();
    try {
        const up = await call('/uploads', { json: { space_id: job.spaceId, parent_id: job.folderId, name: job.file.name, size: job.file.size } });
        job.uploadId = up.id;
        let offset = up.received;
        const CH = up.chunk_size;
        while (offset < job.file.size) {
            if (job.status !== 'uploading') return;
            const index = Math.floor(offset / CH);
            const end = Math.min(offset + CH, job.file.size);
            offset = await sendChunkWithRetry(job, index, job.file.slice(index * CH, end), index * CH);
        }
        if (job.status !== 'uploading') return;
        await call(`/uploads/${job.uploadId}/complete`, { json: {} });
        job.status = 'done';
        job.loaded = job.file.size;
        if (job.spaceId === cur.spaceId && job.folderId === cur.folderId) refreshSoon();
    } catch (e) {
        if (job.status === 'cancelled') return;
        job.status = 'error';
        job.error = e.message || 'Upload failed';
    } finally {
        paintSoon();
        pump();
    }
}

async function sendChunkWithRetry(job, index, blob, base) {
    for (let attempt = 0; ; attempt++) {
        try {
            const res = await sendChunk(job, index, blob, base);
            return res.received;
        } catch (e) {
            if (job.status !== 'uploading') throw e;
            if (e.code === 'OUT_OF_ORDER') return (await call(`/uploads/${job.uploadId}`)).received;
            const retryable = e.status === 0 || e.status >= 500 || e.code === 'INCOMPLETE_CHUNK';
            if (!retryable || attempt >= 6) throw e;
            job.error = 'Connection lost, retrying…';
            paintSoon();
            await sleep(Math.min(16000, 1000 * 2 ** attempt));
            try { return (await call(`/uploads/${job.uploadId}`)).received; } catch { /* try the chunk again */ }
        }
    }
}

function sendChunk(job, index, blob, base) {
    return new Promise((resolve, reject) => {
        const x = new XMLHttpRequest();
        job.xhr = x;
        x.open('PUT', `${API}/uploads/${job.uploadId}/chunks/${index}`);
        x.setRequestHeader('X-WiFiDrop', '1');
        x.setRequestHeader('Content-Type', 'application/octet-stream');
        x.upload.onprogress = e => { job.loaded = base + e.loaded; job.error = ''; paintSoon(); };
        x.onload = () => {
            let data = null;
            try { data = JSON.parse(x.responseText); } catch { /* ignore */ }
            if (x.status >= 200 && x.status < 300) return resolve(data);
            const err = (data && data.error) || {};
            if (x.status === 401) signedOut();
            reject(new FD.ApiError(x.status, err.code || 'ERROR', err.message || `Error ${x.status}`, err.details));
        };
        x.onerror = () => reject(new FD.ApiError(0, 'NETWORK', 'Connection lost'));
        x.onabort = () => reject(new FD.ApiError(0, 'ABORTED', 'Cancelled'));
        x.send(blob);
    });
}

function cancelJob(job, silent = false) {
    const wasActive = job.status === 'uploading' || job.status === 'queued';
    job.status = 'cancelled';
    job.xhr?.abort();
    if (wasActive && job.uploadId && !silent) FD.api(`${API}/uploads/${job.uploadId}`, { method: 'DELETE' }).catch(() => {});
    paintSoon();
    pump();
}

$('#clearDone').onclick = () => {
    for (let i = jobs.length - 1; i >= 0; i--) if (['done', 'cancelled'].includes(jobs[i].status)) jobs.splice(i, 1);
    if (!jobs.length) $('#queueCard').hidden = true;
    paintSoon();
};

let refreshTimer = null;
function refreshSoon() { clearTimeout(refreshTimer); refreshTimer = setTimeout(refresh, 400); }

let painting = false;
function paintSoon() { if (!painting) { painting = true; requestAnimationFrame(paint); } }

function paint() {
    painting = false;
    const total = jobs.reduce((a, j) => a + (j.status === 'cancelled' ? 0 : j.file.size), 0);
    const loaded = jobs.reduce((a, j) => a + (j.status === 'cancelled' ? 0 : j.loaded), 0);
    const done = jobs.filter(j => j.status === 'done').length;
    const failed = jobs.filter(j => j.status === 'error').length;
    const active = jobs.filter(j => j.status === 'uploading' || j.status === 'queued').length;
    $('#overallBar').style.width = (total ? (loaded / total) * 100 : 0) + '%';
    $('#queueSummary').textContent = `${done} of ${jobs.filter(j => j.status !== 'cancelled').length} done` +
        (active ? ` · ${FD.fmtSize(loaded)} of ${FD.fmtSize(total)}` : '') + (failed ? ` · ${failed} failed` : '');
    $('#queue').innerHTML = jobs.map(j => {
        const pct = j.file.size ? (j.loaded / j.file.size) * 100 : (j.status === 'done' ? 100 : 0);
        let sub;
        if (j.status === 'queued') sub = `Waiting · ${FD.fmtSize(j.file.size)}`;
        else if (j.status === 'uploading') {
            const secs = (Date.now() - j.started) / 1000, speed = j.loaded / Math.max(secs, .5);
            sub = j.error || `${FD.fmtSize(j.loaded)} of ${FD.fmtSize(j.file.size)} · ${FD.fmtSize(speed)}/s · ${FD.fmtTime((j.file.size - j.loaded) / Math.max(speed, 1))} left`;
        } else if (j.status === 'done') sub = `Uploaded to ${FD.esc(j.dest)} · ${FD.fmtSize(j.file.size)}`;
        else if (j.status === 'cancelled') sub = 'Cancelled';
        else sub = FD.esc(j.error);
        const kind = FD.kindOf(j.file.name);
        const btn = (j.status === 'uploading' || j.status === 'queued')
            ? `<button class="btn ghost small icon-only" data-cancel="${j.id}" aria-label="Cancel">${FD.icon('x')}</button>`
            : j.status === 'error' ? `<button class="btn ghost small" data-retry="${j.id}">Retry</button>`
            : j.status === 'done' ? FD.icon('check', 'go') : '';
        return `<li class="job" data-status="${j.status === 'uploading' || j.status === 'queued' ? 'active' : j.status}">
            ${FD.icon(kind, `kind ${kind}`)}
            <div class="meta"><span class="name">${FD.esc(j.file.name)}</span><span class="sub">${sub}</span>
            <div class="bar"><span style="width:${pct}%"></span></div></div>
            <div class="row-actions">${btn}</div></li>`;
    }).join('');
    $('#queue').querySelectorAll('[data-cancel]').forEach(b => b.onclick = () => cancelJob(jobs.find(j => j.id == b.dataset.cancel)));
    $('#queue').querySelectorAll('[data-retry]').forEach(b => b.onclick = () => {
        const j = jobs.find(x => x.id == b.dataset.retry);
        Object.assign(j, { status: 'queued', loaded: 0, error: '', uploadId: null });
        pump();
        paintSoon();
    });
}

window.addEventListener('beforeunload', e => {
    if (jobs.some(j => j.status === 'uploading' || j.status === 'queued')) { e.preventDefault(); e.returnValue = ''; }
});

// Drag and drop (desktop browsers)
let dragDepth = 0;
window.addEventListener('dragenter', e => { if (e.dataTransfer?.types.includes('Files')) { dragDepth++; document.body.classList.add('dragging'); } });
window.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; document.body.classList.remove('dragging'); } });
window.addEventListener('dragover', e => e.preventDefault());
window.addEventListener('drop', e => {
    e.preventDefault();
    dragDepth = 0;
    document.body.classList.remove('dragging');
    if (me && !$('#appView').hidden) addFiles([...e.dataTransfer.files]);
});

boot();
