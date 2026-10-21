// Shared helpers for the user page and the admin window.
const FD = (() => {
    // Feather-style icons (MIT), drawn with currentColor so they follow the theme.
    const ICONS = {
        folder: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
        folderPlus: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>',
        file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
        doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
        image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
        video: '<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/>',
        audio: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
        archive: '<polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/>',
        download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
        upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
        trash: '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
        lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
        refresh: '<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>',
        chevron: '<polyline points="9 18 15 12 9 6"/>',
        x: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
        check: '<polyline points="20 6 9 17 4 12"/>',
        alert: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
        edit: '<path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>',
        home: '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
        copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
        user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
        users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
        share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>',
        grid: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
        activity: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
        power: '<path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>',
        logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
        key: '<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>',
        plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
        restore: '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>',
        pause: '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>',
        hdd: '<line x1="22" y1="12" x2="2" y2="12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/><line x1="6" y1="16" x2="6.01" y2="16"/><line x1="10" y1="16" x2="10.01" y2="16"/>',
        ban: '<circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>',
        move: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><polyline points="12 10 15 13 12 16"/><line x1="8" y1="13" x2="15" y2="13"/>',
        more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
        search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
        eye: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
        play: '<polygon points="6 4 20 12 6 20 6 4"/>',
        external: '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
    };

    const icon = (name, cls = '') =>
        `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.file}</svg>`;

    function hydrate(root = document) {
        root.querySelectorAll('[data-icon]').forEach(el => { el.outerHTML = icon(el.dataset.icon); });
    }

    class ApiError extends Error {
        constructor(status, code, message, details) { super(message); this.status = status; this.code = code; this.details = details || {}; }
    }

    async function api(url, opts = {}) {
        const o = { method: opts.method || (opts.json !== undefined ? 'POST' : 'GET'), headers: { 'X-WiFiDrop': '1' }, credentials: 'same-origin' };
        if (opts.json !== undefined) { o.body = JSON.stringify(opts.json); o.headers['Content-Type'] = 'application/json'; }
        let r;
        try { r = await fetch(url, o); } catch { throw new ApiError(0, 'NETWORK', "Can't reach the server. Is WiFiDrop still running?"); }
        let data = null;
        try { data = await r.json(); } catch { /* not JSON */ }
        if (!r.ok) {
            const e = (data && data.error) || {};
            throw new ApiError(r.status, e.code || 'ERROR', e.message || `Error ${r.status}`, e.details);
        }
        return data;
    }

    function fmtSize(b) {
        if (b == null) return '';
        if (b < 1024) return `${b} B`;
        const units = ['KB', 'MB', 'GB', 'TB'];
        let i = -1;
        do { b /= 1024; i++; } while (b >= 1024 && i < units.length - 1);
        return `${b.toFixed(b < 10 ? 1 : 0)} ${units[i]}`;
    }

    function fmtDate(ms) {
        if (!ms) return '';
        const d = new Date(ms), now = new Date();
        if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
        const opts = { month: 'short', day: 'numeric' };
        if (d.getFullYear() !== now.getFullYear()) opts.year = 'numeric';
        return d.toLocaleDateString([], opts);
    }

    function fmtAgo(ms) {
        if (!ms) return 'never';
        const s = Math.max(0, (Date.now() - ms) / 1000);
        if (s < 60) return 'just now';
        if (s < 3600) return `${Math.floor(s / 60)} min ago`;
        if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
        return fmtDate(ms);
    }

    function fmtTime(sec) {
        if (!isFinite(sec) || sec < 0) return '';
        if (sec < 60) return `${Math.ceil(sec)} s`;
        if (sec < 3600) return `${Math.floor(sec / 60)} min ${Math.round(sec % 60)} s`;
        return `${Math.floor(sec / 3600)} h ${Math.round((sec % 3600) / 60)} min`;
    }

    const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    const KINDS = {
        image: 'jpg jpeg png gif webp heic heif bmp tif tiff svg avif raw dng',
        video: 'mp4 mov m4v avi mkv webm 3gp wmv',
        audio: 'mp3 m4a wav aac flac ogg opus',
        archive: 'zip rar 7z tar gz bz2 xz',
        doc: 'pdf doc docx txt rtf md xls xlsx csv ppt pptx pages numbers key odt',
    };
    function kindOf(name) {
        const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
        for (const [k, list] of Object.entries(KINDS)) if (list.split(' ').includes(ext)) return k;
        return 'file';
    }

    function toast(msg, kind = 'ok') {
        const box = document.getElementById('toasts');
        const el = document.createElement('div');
        el.className = `toast ${kind}`;
        el.innerHTML = `${icon(kind === 'err' ? 'alert' : 'check')}<span>${esc(msg)}</span>`;
        box.appendChild(el);
        setTimeout(() => el.classList.add('out'), kind === 'err' ? 5000 : 2600);
        setTimeout(() => el.remove(), kind === 'err' ? 5400 : 3000);
    }

    // Promise-based dialogs built on <dialog>. fields: [{name, label, type, value, placeholder, options}]
    function dialog({ title, body = '', fields = [], ok = 'OK', danger = false, cancel = 'Cancel' }) {
        return new Promise(resolve => {
            const d = document.createElement('dialog');
            d.className = 'dlg';
            const inputs = fields.map(f => {
                const id = `f_${f.name}`;
                if (f.type === 'select') {
                    return `<label class="label" for="${id}">${esc(f.label)}</label><select class="input" id="${id}" name="${f.name}">${
                        f.options.map(o => `<option value="${esc(o.value)}"${o.value === f.value ? ' selected' : ''}>${esc(o.label)}</option>`).join('')}</select>`;
                }
                if (f.type === 'checkbox') {
                    return `<label class="check"><input type="checkbox" id="${id}" name="${f.name}"${f.value ? ' checked' : ''}> ${esc(f.label)}</label>`;
                }
                return `<label class="label" for="${id}">${esc(f.label)}</label><input class="input" id="${id}" name="${f.name}" type="${f.type || 'text'}" value="${esc(f.value ?? '')}" placeholder="${esc(f.placeholder || '')}" autocomplete="off" ${f.attrs || ''}>`;
            }).join('');
            d.innerHTML = `<form method="dialog"><h2>${esc(title)}</h2>${body ? `<p class="muted">${body}</p>` : ''}<div class="fields">${inputs}</div>
                <p class="error dlg-error" hidden></p>
                <div class="dlg-actions">${cancel ? `<button class="btn ghost" value="cancel" type="button" data-cancel>${esc(cancel)}</button>` : ''}
                <button class="btn ${danger ? 'danger-solid' : 'primary'}" value="ok">${esc(ok)}</button></div></form>`;
            document.body.appendChild(d);
            const form = d.querySelector('form');
            const finish = v => { d.close(); d.remove(); resolve(v); };
            d.querySelector('[data-cancel]')?.addEventListener('click', () => finish(null));
            d.addEventListener('cancel', e => { e.preventDefault(); finish(null); });
            form.addEventListener('submit', e => {
                e.preventDefault();
                const out = {};
                fields.forEach(f => {
                    const el = form.elements[f.name];
                    out[f.name] = f.type === 'checkbox' ? el.checked : el.value;
                });
                finish(out);
            });
            d.showModal();
            const first = form.querySelector('input:not([type=checkbox]), select');
            if (first) { first.focus(); if (first.select) first.select(); }
        });
    }

    // Action sheet: sheet('photo.jpg', [{key, label, icon, danger}]) resolves to the chosen key or null.
    function sheet(title, actions) {
        return new Promise(resolve => {
            const d = document.createElement('dialog');
            d.className = 'sheet';
            d.innerHTML = `<div class="sheet-title">${esc(title)}</div>` +
                actions.map(a => `<button type="button" data-k="${a.key}" class="${a.danger ? 'danger' : ''}">${icon(a.icon)} ${esc(a.label)}</button>`).join('') +
                `<button type="button" class="cancel" data-k="">Cancel</button>`;
            document.body.appendChild(d);
            const finish = v => { d.close(); d.remove(); resolve(v); };
            d.querySelectorAll('button').forEach(b => b.onclick = () => finish(b.dataset.k || null));
            d.addEventListener('cancel', e => { e.preventDefault(); finish(null); });
            d.addEventListener('click', e => { if (e.target === d) finish(null); });
            d.showModal();
        });
    }

    const confirmBox = (title, body, ok = 'Delete', danger = true) =>
        dialog({ title, body, ok, danger }).then(v => v !== null);

    // ---------- previews: thumbnails in lists and a viewer for pictures, videos and audio

    const PREVIEW_KEY = 'wd_previews';
    function previewsOn() {
        try { return localStorage.getItem(PREVIEW_KEY) !== 'off'; } catch { return true; }
    }
    function setPreviews(on) {
        try { localStorage.setItem(PREVIEW_KEY, on ? 'on' : 'off'); } catch { /* private mode: just this visit */ }
    }

    // What the browser can show inside the page (the PC only serves these types inline).
    const VIEWABLE = { image: 'jpg jpeg png gif webp bmp', video: 'mp4 m4v mov webm', audio: 'mp3 m4a wav' };
    function viewable(name) {
        const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
        for (const [k, list] of Object.entries(VIEWABLE)) if (list.split(' ').includes(ext)) return k;
        return null;
    }
    // Pictures and videos may have a thumbnail (the PC makes them for pictures; the phone app for HEIC and videos).
    const hasThumb = name => ['image', 'video'].includes(kindOf(name));

    /** The file-type icon, swapped for a thumbnail once (and if) one loads. */
    function thumb(kindIcon, src) {
        const img = src ? `<img class="thumb" src="${src}" alt="" loading="lazy" decoding="async">` : '';
        return `<span class="thumb-wrap">${kindIcon}${img}</span>`;
    }
    function wireThumbs(root) {
        root.querySelectorAll('img.thumb').forEach(img => {
            const done = () => img.closest('.thumb-wrap')?.classList.add('loaded');
            if (img.complete && img.naturalWidth) done();
            else {
                img.addEventListener('load', done, { once: true });
                img.addEventListener('error', () => img.remove(), { once: true });
            }
        });
    }

    /** Full-screen viewer with a download button. kind: image, video or audio. */
    function viewer({ name, src, kind, download }) {
        const d = document.createElement('dialog');
        d.className = 'viewer';
        const media = kind === 'image' ? `<img src="${src}" alt="${esc(name)}">`
            : kind === 'video' ? `<video src="${src}" controls autoplay playsinline></video>`
            : `<audio src="${src}" controls autoplay></audio>`;
        d.innerHTML = `<div class="viewer-bar"><b>${esc(name)}</b>
            <a class="btn ghost small" href="${download}" download>${icon('download')} Download</a>
            <button class="btn ghost small icon-only" type="button" aria-label="Close">${icon('x')}</button></div>
            <div class="viewer-body">${media}</div>`;
        document.body.appendChild(d);
        const close = () => { d.querySelectorAll('video, audio').forEach(m => m.pause()); d.close(); d.remove(); };
        d.querySelector('button').onclick = close;
        d.addEventListener('cancel', e => { e.preventDefault(); close(); });
        d.querySelector('.viewer-body').addEventListener('click', e => { if (e.target.classList.contains('viewer-body')) close(); });
        const m = d.querySelector('.viewer-body > *');
        m.addEventListener('error', () => {
            d.querySelector('.viewer-body').innerHTML = `<p class="muted">This file can't be shown here. Download it to open it.</p>`;
        }, { once: true });
        d.showModal();
    }

    return { icon, hydrate, api, ApiError, fmtSize, fmtDate, fmtAgo, fmtTime, esc, kindOf, toast, dialog, confirmBox, sheet,
             previewsOn, setPreviews, viewable, hasThumb, thumb, wireThumbs, viewer };
})();
