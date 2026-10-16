// Feedback inbox: review, triage, reply to and close website submissions.
(function () {
    "use strict";
    const $ = s => document.querySelector(s);
    const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const when = t => new Date(t * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    const LABELS = { bug: "Bug", idea: "Idea", question: "Question", general: "General", partnership: "Partnership",
        press: "Press", privacy: "Privacy", signup: "Beta", new: "New", in_progress: "In progress", closed: "Closed" };
    let kind = "feedback", selected = null, items = [];

    async function api(url, opts = {}) {
        const o = { method: opts.method || (opts.json ? "POST" : "GET"), headers: {} };
        if (opts.json !== undefined) { o.body = JSON.stringify(opts.json); o.headers["Content-Type"] = "application/json"; }
        const r = await fetch(url, o);
        const data = await r.json().catch(() => ({}));
        if (r.status === 401 && url !== "/admin/api/login") { showLogin(); throw new Error("Please sign in."); }
        if (!r.ok) throw new Error(data.message || "Error " + r.status);
        return data;
    }
    function toast(msg) {
        const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.appendChild(t);
        setTimeout(() => t.remove(), 2200);
    }

    function showLogin() { $("#app").hidden = true; $("#login").hidden = false; $("#pw").focus(); }
    $("#loginForm").addEventListener("submit", async e => {
        e.preventDefault();
        try { await api("/admin/api/login", { json: { password: $("#pw").value } }); $("#pw").value = ""; start(); }
        catch (err) { $("#loginError").textContent = err.message; $("#loginError").hidden = false; }
    });
    $("#logout").onclick = async () => { await api("/admin/api/logout", { json: {} }).catch(() => {}); showLogin(); };

    document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => {
        kind = b.dataset.kind;
        document.querySelectorAll("#tabs button").forEach(x => x.setAttribute("aria-current", String(x === b)));
        selected = null;
        $("#detail").innerHTML = '<p class="muted">Select an item to see it.</p>';
        load();
    });
    $("#status").onchange = load;
    let t = null;
    $("#search").oninput = () => { clearTimeout(t); t = setTimeout(load, 250); };

    async function counts() {
        const s = await api("/admin/api/summary");
        for (const k of ["feedback", "contact", "beta"]) {
            const n = s.counts[`${k}:new`] || 0;
            document.querySelector(`[data-count="${k}"]`).textContent = n ? n : "";
        }
        document.querySelector('[data-count="waitlist"]').textContent = s.waitlist || "";
    }

    async function load() {
        const isWaitlist = kind === "waitlist";
        $("#status").hidden = isWaitlist;
        $("#export").href = `/admin/api/export.csv?kind=${kind}`;
        if (isWaitlist) {
            items = (await api("/admin/api/waitlist")).items;
            const q = $("#search").value.toLowerCase();
            items = items.filter(i => !q || i.email.includes(q));
            $("#list").innerHTML = items.map(i => `<li data-id="${i.id}"><div class="row1"><span>${i.unsubscribed_at ? "Unsubscribed" : "Subscribed"}</span><span>${when(i.consent_at)}</span></div><div class="title">${esc(i.email)}</div></li>`).join("");
        } else {
            const params = new URLSearchParams({ kind, status: $("#status").value, q: $("#search").value });
            items = (await api("/admin/api/submissions?" + params)).items;
            $("#list").innerHTML = items.map(i => `<li data-id="${i.id}" aria-selected="${i.id === selected}">
                <div class="row1"><span><span class="badge ${i.category}">${LABELS[i.category] || i.category}</span> <span class="badge ${i.status}">${LABELS[i.status]}</span>${i.attachment_count ? " · 📎" : ""}</span><span>${when(i.created_at)}</span></div>
                <div class="title">${esc(i.subject || i.message.slice(0, 80) || i.name)}</div>
                <div class="muted">${esc(i.name || i.email || "Anonymous")}</div></li>`).join("");
        }
        $("#empty").hidden = items.length > 0;
        document.querySelectorAll("#list li").forEach(li => li.onclick = () => open(Number(li.dataset.id)));
        counts().catch(() => {});
    }

    async function open(id) {
        selected = id;
        document.querySelectorAll("#list li").forEach(li => li.setAttribute("aria-selected", String(Number(li.dataset.id) === id)));
        if (kind === "waitlist") return openWaitlist(items.find(i => i.id === id));
        const s = await api(`/admin/api/submissions/${id}`);
        const d = s.details || {};
        const rows = [["Received", when(s.created_at)], ["Type", LABELS[s.category] || s.category], ["Name", s.name], ["Email", s.email],
            ["App version", d.app_version], ["Windows", d.windows], ["Phone or browser", d.device],
            ["Devices", (d.phones || []).join(", ")]].filter(([, v]) => v);
        const reply = s.email ? `mailto:${encodeURIComponent(s.email)}?subject=${encodeURIComponent("Re: " + (s.subject || "your FileDrop " + (LABELS[s.category] || "message").toLowerCase()))}` : "";
        $("#detail").innerHTML = `
            <h2>${esc(s.subject || LABELS[s.category] || "Submission")}</h2>
            <dl class="meta">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
            <div class="message">${esc(s.message)}</div>
            ${d.steps ? `<div><label>Steps to reproduce</label><div class="message">${esc(d.steps)}</div></div>` : ""}
            ${s.attachments.length ? `<div><label>Attachments (open only if you trust them)</label><div class="actions">${s.attachments.map(a =>
                `<a class="btn" href="/admin/api/attachments/${a.id}">📎 ${esc(a.filename)} · ${a.size_bytes < 1024 ? a.size_bytes + " bytes" : (a.size_bytes / 1024).toFixed(0) + " KB"}</a>`).join("")}</div></div>` : ""}
            <div><label for="note">Private note</label><textarea id="note" placeholder="Only visible here">${esc(s.admin_note)}</textarea></div>
            <div class="actions">
                <select id="setStatus">${["new", "in_progress", "closed"].map(v => `<option value="${v}"${v === s.status ? " selected" : ""}>${LABELS[v]}</option>`).join("")}</select>
                <button class="btn primary" id="save" type="button">Save</button>
                ${reply ? `<a class="btn" href="${reply}">Reply by email</a>` : ""}
                <button class="btn danger" id="del" type="button">Delete for good</button>
            </div>`;
        $("#save").onclick = async () => {
            await api(`/admin/api/submissions/${id}`, { method: "PATCH", json: { status: $("#setStatus").value, admin_note: $("#note").value } });
            toast("Saved"); load();
        };
        $("#del").onclick = async () => {
            if (!confirm("Delete this submission and its attachments for good? Use this for privacy requests.")) return;
            await api(`/admin/api/submissions/${id}`, { method: "DELETE" });
            toast("Deleted"); $("#detail").innerHTML = ""; load();
        };
    }

    function openWaitlist(w) {
        $("#detail").innerHTML = `<h2>${esc(w.email)}</h2>
            <dl class="meta"><dt>Consent given</dt><dd>${when(w.consent_at)}</dd><dt>Status</dt><dd>${w.unsubscribed_at ? "Unsubscribed " + when(w.unsubscribed_at) : "Subscribed"}</dd>
            <dt>Unsubscribe link</dt><dd>${esc(w.unsubscribe_url)}</dd></dl>
            <p class="muted">Include the unsubscribe link in every email you send (CASL).</p>
            <div class="actions"><button class="btn danger" id="wdel" type="button">Delete address</button></div>`;
        $("#wdel").onclick = async () => {
            if (!confirm("Delete this email address from the waitlist?")) return;
            await api(`/admin/api/waitlist/${w.id}`, { method: "DELETE" }); toast("Deleted"); $("#detail").innerHTML = ""; load();
        };
    }

    function start() { $("#login").hidden = true; $("#app").hidden = false; load(); }
    api("/admin/api/summary").then(start).catch(showLogin);
})();
