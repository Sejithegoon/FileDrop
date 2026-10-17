// Feedback inbox for the website: signs in with Supabase Auth and reads the forms tables.
// Row-level security means only accounts listed in public.admins can see or change anything.
(function () {
    "use strict";
    const $ = s => document.querySelector(s);
    const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const when = t => t ? new Date(t).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "";
    const LABELS = { bug: "Bug", idea: "Idea", question: "Question", general: "General", partnership: "Partnership",
        press: "Press", privacy: "Privacy", signup: "Beta", new: "New", in_progress: "In progress", closed: "Closed" };
    const S = window.SITE || {};
    const BASE = (S.supabaseUrl || "").replace(/\/$/, "");
    const KEY = S.supabaseKey || "";
    const SITE_URL = location.href.replace(/admin\.html.*$/, "");
    let kind = "feedback", selected = null, items = [];
    let session = null;
    try { session = JSON.parse(sessionStorage.getItem("fd-inbox") || "null"); } catch { /* storage blocked */ }

    function saveSession(s) {
        session = s;
        try { s ? sessionStorage.setItem("fd-inbox", JSON.stringify(s)) : sessionStorage.removeItem("fd-inbox"); } catch { /* ignore */ }
    }

    async function auth(grant, body) {
        const r = await fetch(`${BASE}/auth/v1/token?grant_type=${grant}`, {
            method: "POST", headers: { apikey: KEY, "Content-Type": "application/json" }, body: JSON.stringify(body),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error_description || data.msg || data.message || "Sign-in failed.");
        saveSession({ access: data.access_token, refresh: data.refresh_token });
    }

    // Calls Supabase with the signed-in user's token, refreshing it once if it has expired.
    async function call(path, opts = {}, retry = true) {
        if (!session) { showLogin(); throw new Error("Please sign in."); }
        const headers = { apikey: KEY, Authorization: `Bearer ${session.access}`, ...(opts.headers || {}) };
        if (opts.json !== undefined) headers["Content-Type"] = "application/json";
        const r = await fetch(BASE + path, { method: opts.method || "GET", headers,
            body: opts.json !== undefined ? JSON.stringify(opts.json) : undefined });
        if ((r.status === 401 || r.status === 403) && retry && session.refresh) {
            try { await auth("refresh_token", { refresh_token: session.refresh }); } catch { saveSession(null); showLogin(); throw new Error("Please sign in again."); }
            return call(path, opts, false);
        }
        if (r.status === 401) { saveSession(null); showLogin(); throw new Error("Please sign in again."); }
        if (!r.ok) {
            const data = await r.json().catch(() => ({}));
            throw new Error(data.message || data.error || "Error " + r.status);
        }
        return r;
    }
    const rest = async (path, opts) => {
        const r = await call("/rest/v1/" + path, opts);
        return r.status === 204 || opts?.method === "HEAD" ? r : r.json();
    };
    async function count(path) {
        const r = await call("/rest/v1/" + path, { method: "HEAD", headers: { Prefer: "count=exact" } });
        return Number((r.headers.get("content-range") || "*/0").split("/")[1] || 0);
    }

    function toast(msg) {
        const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.appendChild(t);
        setTimeout(() => t.remove(), 2200);
    }
    const fail = err => toast(err.message || String(err));

    function showLogin(message) {
        $("#app").hidden = true; $("#login").hidden = false;
        if (message) { $("#loginError").textContent = message; $("#loginError").hidden = false; }
        $("#em").focus();
    }
    $("#loginForm").addEventListener("submit", async e => {
        e.preventDefault();
        $("#loginError").hidden = true;
        try {
            if (!BASE || !KEY) throw new Error("Add supabaseUrl and supabaseKey to assets/js/config.js first.");
            await auth("password", { email: $("#em").value.trim(), password: $("#pw").value });
            $("#pw").value = "";
            await start();
        } catch (err) { showLogin(err.message); }
    });
    $("#logout").onclick = async () => {
        if (session) await fetch(`${BASE}/auth/v1/logout`, { method: "POST", headers: { apikey: KEY, Authorization: `Bearer ${session.access}` } }).catch(() => {});
        saveSession(null); showLogin();
    };

    document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => {
        kind = b.dataset.kind;
        document.querySelectorAll("#tabs button").forEach(x => x.setAttribute("aria-current", String(x === b)));
        selected = null;
        $("#detail").innerHTML = '<p class="muted">Select an item to see it.</p>';
        load().catch(fail);
    });
    $("#status").onchange = () => load().catch(fail);
    let timer = null;
    $("#search").oninput = () => { clearTimeout(timer); timer = setTimeout(() => load().catch(fail), 250); };

    async function counts() {
        for (const k of ["feedback", "contact", "beta"]) {
            const n = await count(`submissions?select=id&kind=eq.${k}&status=eq.new`);
            document.querySelector(`[data-count="${k}"]`).textContent = n || "";
        }
        document.querySelector('[data-count="waitlist"]').textContent = (await count("waitlist?select=id&unsubscribed_at=is.null")) || "";
    }

    // PostgREST filter for the search box. Characters with meaning in the filter syntax are dropped.
    function searchFilter(fields) {
        const q = $("#search").value.replace(/[,()*\\"':.%]/g, " ").trim();
        if (!q) return "";
        return "&or=" + encodeURIComponent(`(${fields.map(f => `${f}.ilike.*${q}*`).join(",")})`);
    }

    function query(limit) {
        if (kind === "waitlist") return `waitlist?select=*&order=consent_at.desc&limit=${limit}${searchFilter(["email"])}`;
        if (kind === "licences") return `licences?select=*,activations(install_id,app_version,activated_at,last_seen_at)&order=issued_at.desc&limit=${limit}${searchFilter(["email", "id", "note"])}`;
        const status = $("#status").value;
        return `submissions?select=*,attachments(id,filename,content_type,size_bytes,storage_path)&kind=eq.${kind}`
            + (status ? `&status=eq.${status}` : "") + `&order=created_at.desc&limit=${limit}`
            + searchFilter(["subject", "message", "name", "email"]);
    }

    async function load() {
        const isWaitlist = kind === "waitlist";
        $("#status").hidden = isWaitlist || kind === "licences";
        $("#issue").hidden = kind !== "licences";
        items = await rest(query(500));
        if (kind === "licences") {
            $("#list").innerHTML = items.map(i => `<li data-id="${esc(i.id)}" aria-selected="${i.id === selected}"><div class="row1"><span>${i.revoked_at ? '<span class="badge bug">Revoked</span>' : '<span class="badge idea">Active</span>'} ${i.activations.length}/${i.max_activations} PCs</span><span>${when(i.issued_at)}</span></div><div class="title">${esc(i.email)}</div><div class="muted">${esc(i.id)}${i.note ? " · " + esc(i.note) : ""}</div></li>`).join("");
        } else if (isWaitlist) {
            $("#list").innerHTML = items.map(i => `<li data-id="${i.id}" aria-selected="${i.id === selected}"><div class="row1"><span>${i.unsubscribed_at ? "Unsubscribed" : "Subscribed"}</span><span>${when(i.consent_at)}</span></div><div class="title">${esc(i.email)}</div></li>`).join("");
        } else {
            $("#list").innerHTML = items.map(i => `<li data-id="${i.id}" aria-selected="${i.id === selected}">
                <div class="row1"><span><span class="badge ${esc(i.category)}">${esc(LABELS[i.category] || i.category)}</span> <span class="badge ${esc(i.status)}">${LABELS[i.status]}</span>${i.attachments.length ? " · 📎" : ""}</span><span>${when(i.created_at)}</span></div>
                <div class="title">${esc(i.subject || i.message.slice(0, 80) || i.name)}</div>
                <div class="muted">${esc(i.name || i.email || "Anonymous")}</div></li>`).join("");
        }
        $("#empty").hidden = items.length > 0;
        document.querySelectorAll("#list li").forEach(li => li.onclick = () => open(kind === "licences" ? li.dataset.id : Number(li.dataset.id)));
        counts().catch(() => {});
    }

    const size = n => n < 1024 ? n + " bytes" : (n / 1024).toFixed(0) + " KB";

    // Attachments are downloaded (never shown inline) because they come from the public.
    async function download(a) {
        const r = await call(`/storage/v1/object/authenticated/attachments/${a.storage_path}`);
        const url = URL.createObjectURL(await r.blob());
        const link = Object.assign(document.createElement("a"), { href: url, download: a.filename });
        document.body.appendChild(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 10000);
    }

    function open(id) {
        selected = id;
        document.querySelectorAll("#list li").forEach(li => li.setAttribute("aria-selected", String(li.dataset.id === String(id))));
        const s = items.find(i => i.id === id);
        if (!s) return;
        if (kind === "waitlist") return openWaitlist(s);
        if (kind === "licences") return openLicence(s);
        const d = s.details || {};
        const rows = [["Received", when(s.created_at)], ["Type", LABELS[s.category] || s.category], ["Name", s.name], ["Email", s.email],
            ["App version", d.app_version], ["Windows", d.windows], ["Phone or browser", d.device],
            ["Devices", (d.phones || []).join(", ")], ["Consent", d.consent_at ? when(d.consent_at) : ""]].filter(([, v]) => v);
        const reply = s.email ? `mailto:${encodeURIComponent(s.email)}?subject=${encodeURIComponent("Re: " + (s.subject || "your FileDrop " + (LABELS[s.category] || "message").toLowerCase()))}` : "";
        $("#detail").innerHTML = `
            <h2>${esc(s.subject || LABELS[s.category] || "Submission")}</h2>
            <dl class="meta">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
            <div class="message">${esc(s.message)}</div>
            ${d.steps ? `<div><label>Steps to reproduce</label><div class="message">${esc(d.steps)}</div></div>` : ""}
            ${s.attachments.length ? `<div><label>Attachments (open only if you trust them)</label><div class="actions">${s.attachments.map((a, n) =>
                `<button class="btn" type="button" data-file="${n}">📎 ${esc(a.filename)} · ${size(a.size_bytes)}</button>`).join("")}</div></div>` : ""}
            <div><label for="note">Private note</label><textarea id="note" placeholder="Only visible here">${esc(s.admin_note)}</textarea></div>
            <div class="actions">
                <select id="setStatus">${["new", "in_progress", "closed"].map(v => `<option value="${v}"${v === s.status ? " selected" : ""}>${LABELS[v]}</option>`).join("")}</select>
                <button class="btn primary" id="save" type="button">Save</button>
                ${reply ? `<a class="btn" href="${reply}">Reply by email</a>` : ""}
                <button class="btn danger" id="del" type="button">Delete for good</button>
            </div>`;
        document.querySelectorAll("[data-file]").forEach(b => b.onclick = () => download(s.attachments[Number(b.dataset.file)]).catch(fail));
        $("#save").onclick = async () => {
            try {
                await rest(`submissions?id=eq.${id}`, { method: "PATCH", headers: { Prefer: "return=minimal" },
                    json: { status: $("#setStatus").value, admin_note: $("#note").value, updated_at: new Date().toISOString() } });
                toast("Saved"); await load();
            } catch (err) { fail(err); }
        };
        $("#del").onclick = async () => {
            if (!confirm("Delete this submission and its attachments for good? Use this for privacy requests.")) return;
            try {
                if (s.attachments.length) {
                    await call("/storage/v1/object/attachments", { method: "DELETE", json: { prefixes: s.attachments.map(a => a.storage_path) } });
                }
                await rest(`submissions?id=eq.${id}`, { method: "DELETE", headers: { Prefer: "return=minimal" } });
                toast("Deleted"); $("#detail").innerHTML = ""; await load();
            } catch (err) { fail(err); }
        };
    }

    function openWaitlist(w) {
        const link = `${SITE_URL}unsubscribe.html?token=${encodeURIComponent(w.unsubscribe_token)}`;
        $("#detail").innerHTML = `<h2>${esc(w.email)}</h2>
            <dl class="meta"><dt>Consent given</dt><dd>${when(w.consent_at)}</dd><dt>Consent wording</dt><dd>${esc(w.consent_text)}</dd>
            <dt>Status</dt><dd>${w.unsubscribed_at ? "Unsubscribed " + when(w.unsubscribed_at) : "Subscribed"}</dd>
            <dt>Unsubscribe link</dt><dd>${esc(link)}</dd></dl>
            <p class="muted">Include the unsubscribe link in every email you send (CASL).</p>
            <div class="actions"><button class="btn danger" id="wdel" type="button">Delete address</button></div>`;
        $("#wdel").onclick = async () => {
            if (!confirm("Delete this email address from the waitlist?")) return;
            try {
                await rest(`waitlist?id=eq.${w.id}`, { method: "DELETE", headers: { Prefer: "return=minimal" } });
                toast("Deleted"); $("#detail").innerHTML = ""; await load();
            } catch (err) { fail(err); }
        };
    }

    // ---- licences
    async function functionCall(path, body) {
        const r = await call(`/functions/v1/licence/${path}`, { method: "POST", json: body });
        return r.json();
    }

    function openLicence(l) {
        $("#detail").innerHTML = `<h2>${esc(l.email)}</h2>
            <dl class="meta"><dt>Licence</dt><dd>${esc(l.id)}</dd><dt>Issued</dt><dd>${when(l.issued_at)}</dd>
            <dt>Updates until</dt><dd>${esc(l.updates_until)}</dd>
            <dt>Status</dt><dd>${l.revoked_at ? "Revoked " + when(l.revoked_at) + (l.revoke_reason ? " (" + esc(l.revoke_reason) + ")" : "") : "Active"}</dd>
            ${l.order_id ? `<dt>Order</dt><dd>${esc(l.order_id)}</dd>` : ""}</dl>
            <div><label>PCs (${l.activations.length} of ${l.max_activations})</label>
            ${l.activations.length ? `<ul class="pcs">${l.activations.map((a, n) => `<li><span>PC ${esc(a.install_id.slice(0, 8))}… · v${esc(a.app_version)} · last seen ${when(a.last_seen_at)}</span><button class="btn" type="button" data-pc="${n}">Remove</button></li>`).join("")}</ul>` : '<p class="muted">Not activated on any PC yet.</p>'}</div>
            <div><label>Licence (send this to the customer)</label><pre class="message licence-text">${esc(l.licence_text)}</pre></div>
            <div><label for="lnote">Private note</label><textarea id="lnote">${esc(l.note)}</textarea></div>
            <div class="actions">
                <button class="btn primary" id="lcopy" type="button">Copy licence</button>
                <a class="btn" href="mailto:${encodeURIComponent(l.email)}?subject=${encodeURIComponent("Your FileDrop Pro licence")}&body=${encodeURIComponent("Open FileDrop, go to Licence, and paste this:\n\n" + l.licence_text)}">Email it</a>
                <button class="btn" id="lsave" type="button">Save note</button>
                <button class="btn danger" id="lrevoke" type="button">${l.revoked_at ? "Restore licence" : "Revoke licence"}</button>
            </div>`;
        $("#lcopy").onclick = () => navigator.clipboard.writeText(l.licence_text).then(() => toast("Copied"), fail);
        const patch = async (fields, msg) => {
            try {
                await rest(`licences?id=eq.${encodeURIComponent(l.id)}`, { method: "PATCH", headers: { Prefer: "return=minimal" }, json: fields });
                toast(msg); await load(); open(l.id);
            } catch (err) { fail(err); }
        };
        $("#lsave").onclick = () => patch({ note: $("#lnote").value }, "Saved");
        $("#lrevoke").onclick = () => {
            if (l.revoked_at) return patch({ revoked_at: null, revoke_reason: "" }, "Licence restored");
            const reason = prompt("Revoke this licence? Pro turns read-only on the customer's PCs at their next check-in.\nReason (for example: refund):", "refund");
            if (reason !== null) patch({ revoked_at: new Date().toISOString(), revoke_reason: reason.slice(0, 200) }, "Licence revoked");
        };
        document.querySelectorAll("[data-pc]").forEach(b => b.onclick = async () => {
            const a = l.activations[Number(b.dataset.pc)];
            if (!confirm("Remove this PC from the licence? The customer can then activate another PC.")) return;
            try {
                await rest(`activations?licence_id=eq.${encodeURIComponent(l.id)}&install_id=eq.${encodeURIComponent(a.install_id)}`,
                    { method: "DELETE", headers: { Prefer: "return=minimal" } });
                toast("PC removed"); await load(); open(l.id);
            } catch (err) { fail(err); }
        });
    }

    $("#issue").onclick = () => {
        selected = null;
        const year = new Date(); year.setFullYear(year.getFullYear() + 1);
        $("#detail").innerHTML = `<h2>Issue a Pro licence</h2>
            <p class="muted">For testing, giveaways and support. Paid licences will be issued automatically once payments are set up.</p>
            <div><label for="iemail">Customer email</label><input id="iemail" type="email" required></div>
            <div><label for="iupd">Updates until</label><input id="iupd" type="date" value="${year.toISOString().slice(0, 10)}"></div>
            <div><label for="imax">PCs</label><input id="imax" type="number" min="1" max="50" value="3"></div>
            <div><label for="inote">Private note</label><input id="inote" placeholder="e.g. beta tester"></div>
            <div class="actions"><button class="btn primary" id="igo" type="button">Issue licence</button></div>`;
        $("#igo").onclick = async () => {
            try {
                $("#igo").disabled = true;
                const r = await functionCall("issue", { email: $("#iemail").value, updates_until: $("#iupd").value,
                    max_activations: Number($("#imax").value), note: $("#inote").value });
                if (!r.ok) throw new Error(r.message);
                toast("Licence issued"); await load(); open(r.id);
            } catch (err) { fail(err); $("#igo").disabled = false; }
        };
    };

    // CSV of everything matching the current tab, status and search (up to 10,000 rows).
    $("#export").onclick = async () => {
        try {
            const rows = await rest(query(10000));
            const cols = kind === "licences" ? ["id", "email", "issued_at", "updates_until", "max_activations", "revoked_at", "revoke_reason", "order_id", "note"]
                : kind === "waitlist"
                ? ["id", "email", "consent_at", "consent_text", "unsubscribed_at"]
                : ["id", "created_at", "category", "status", "name", "email", "subject", "message", "details", "admin_note"];
            const cell = v => {
                let t = v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
                if (/^[=+\-@\t\r]/.test(t)) t = "'" + t;  // stop spreadsheets from running formulas
                return `"${t.replace(/"/g, '""')}"`;
            };
            const csv = [cols.join(","), ...rows.map(r => cols.map(c => cell(r[c])).join(","))].join("\r\n");
            const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv" }));
            const a = Object.assign(document.createElement("a"), { href: url, download: `filedrop-${kind}-${new Date().toISOString().slice(0, 10)}.csv` });
            document.body.appendChild(a); a.click(); a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 10000);
        } catch (err) { fail(err); }
    };

    async function start() {
        const me = await rest("admins?select=user_id");
        if (!me.length) { saveSession(null); throw new Error("This account isn't an inbox admin. Add it to the admins table (see supabase/README.md)."); }
        $("#login").hidden = true; $("#app").hidden = false;
        await load();
    }

    if (!BASE || !KEY) showLogin("The inbox isn't connected yet: add supabaseUrl and supabaseKey to assets/js/config.js.");
    else if (session) start().catch(err => showLogin(err.message));
    else showLogin();
})();
