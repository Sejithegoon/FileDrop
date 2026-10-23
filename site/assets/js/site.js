// WiFiDrop website behaviour. Everything degrades gracefully without JavaScript.
(function () {
    "use strict";
    const S = window.SITE || {};
    const $ = (sel, root = document) => root.querySelector(sel);
    const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const root = document.documentElement;

    // ---------- theme
    const themeBtn = $(".theme-toggle");
    function currentTheme() {
        const set = root.getAttribute("data-theme");
        if (set) return set;
        return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }
    function labelTheme() {
        if (themeBtn) themeBtn.setAttribute("aria-label", currentTheme() === "dark" ? "Switch to light mode" : "Switch to dark mode");
    }
    if (themeBtn) {
        labelTheme();
        themeBtn.addEventListener("click", () => {
            const next = currentTheme() === "dark" ? "light" : "dark";
            root.setAttribute("data-theme", next);
            try { localStorage.setItem("fd-theme", next); } catch (e) { /* storage blocked */ }
            labelTheme();
        });
    }

    // ---------- header: shadow once scrolled, mobile menu
    const header = $(".site-header");
    const onScroll = () => header && header.classList.toggle("scrolled", window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });

    const menuBtn = $(".menu-btn");
    const nav = $(".nav");
    function closeMenu() { nav.classList.remove("open"); menuBtn.setAttribute("aria-expanded", "false"); }
    if (menuBtn && nav) {
        menuBtn.addEventListener("click", () => {
            const open = nav.classList.toggle("open");
            menuBtn.setAttribute("aria-expanded", String(open));
        });
        document.addEventListener("keydown", e => { if (e.key === "Escape") closeMenu(); });
        nav.addEventListener("click", e => { if (e.target.closest("a")) closeMenu(); });
    }

    const here = location.pathname.split("/").pop() || "index.html";
    $$(".nav a[href]").forEach(a => { if (a.getAttribute("href") === here) a.setAttribute("aria-current", "page"); });

    // ---------- values from config.js
    $$("[data-site]").forEach(el => { const v = S[el.dataset.site]; if (v) el.textContent = v; });
    $$("[data-download]").forEach(a => {
        if (S.downloadUrl) {
            a.href = S.downloadUrl;
        } else {
            a.setAttribute("aria-disabled", "true");
            a.removeAttribute("href");
            const label = $("[data-label]", a);
            if (label) label.textContent = "Download coming soon";
        }
    });
    $$("[data-if-download]").forEach(el => { el.hidden = !S.downloadUrl; });
    $$("[data-if-no-download]").forEach(el => { el.hidden = !!S.downloadUrl; });
    $$("[data-email]").forEach(el => {
        if (S.supportEmail) {
            el.textContent = S.supportEmail;
            if (el.tagName === "A") el.href = "mailto:" + S.supportEmail;
        }
    });
    $$("[data-year]").forEach(el => { el.textContent = new Date().getFullYear(); });

    // ---------- reveal on scroll
    const revealEls = $$(".reveal");
    if (!reduceMotion && "IntersectionObserver" in window) {
        const io = new IntersectionObserver(entries => {
            entries.forEach(en => { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
        }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
        revealEls.forEach(el => io.observe(el));
    } else {
        revealEls.forEach(el => el.classList.add("in"));
    }

    // ---------- screenshot tours: tabs switch images, auto-advance until the visitor interacts
    $$(".tour").forEach(tour => {
        const tabs = $$(".tour-tab", tour);
        const imgs = $$(".screen img.swap", tour);
        const ms = Number(tour.dataset.interval || 6000);
        tour.style.setProperty("--tour-ms", ms + "ms");
        let i = 0, timer = null, stopped = reduceMotion;
        function show(n, focus) {
            i = (n + tabs.length) % tabs.length;
            tabs.forEach((t, k) => {
                t.setAttribute("aria-selected", String(k === i));
                t.tabIndex = k === i ? 0 : -1;
                const bar = $(".bar i", t);
                if (bar) { bar.style.animation = "none"; void bar.offsetWidth; bar.style.animation = ""; }
            });
            imgs.forEach((im, k) => im.classList.toggle("active", k === i));
            if (focus) tabs[i].focus();
        }
        function schedule() {
            clearInterval(timer);
            if (!stopped) timer = setInterval(() => show(i + 1), ms);
        }
        tabs.forEach((t, k) => {
            t.addEventListener("click", () => { stopped = true; tour.classList.add("paused"); clearInterval(timer); show(k); });
            t.addEventListener("keydown", e => {
                if (["ArrowDown", "ArrowRight"].includes(e.key)) { e.preventDefault(); stopped = true; show(i + 1, true); }
                if (["ArrowUp", "ArrowLeft"].includes(e.key)) { e.preventDefault(); stopped = true; show(i - 1, true); }
            });
        });
        tour.addEventListener("mouseenter", () => { tour.classList.add("paused"); clearInterval(timer); });
        tour.addEventListener("mouseleave", () => { if (!stopped) { tour.classList.remove("paused"); schedule(); } });
        // only rotate while visible
        if ("IntersectionObserver" in window) {
            new IntersectionObserver(([en]) => { if (en.isIntersecting) schedule(); else clearInterval(timer); }, { threshold: 0.3 }).observe(tour);
        }
        if (stopped) tour.classList.add("paused");
        show(0);
    });

    // ---------- tap a screenshot to see it full size
    const zoomables = $$("img.zoomable");
    if (zoomables.length && "HTMLDialogElement" in window) {
        const box = document.createElement("dialog");
        box.className = "lightbox";
        box.innerHTML = '<button class="icon-btn" type="button" aria-label="Close"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button><img alt="">';
        document.body.appendChild(box);
        const big = $("img", box);
        zoomables.forEach(img => {
            img.tabIndex = 0;
            img.setAttribute("role", "button");
            img.setAttribute("aria-label", (img.alt || "Screenshot") + ". Open full size.");
            const open = () => { big.src = img.currentSrc || img.src; big.alt = img.alt; box.showModal(); };
            img.addEventListener("click", open);
            img.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
        });
        box.addEventListener("click", e => { if (e.target !== big) box.close(); });
    }

    // ---------- copy buttons
    $$("[data-copy]").forEach(btn => {
        btn.addEventListener("click", async () => {
            const target = $(btn.dataset.copy);
            const text = target ? target.textContent.trim() : "";
            try {
                await navigator.clipboard.writeText(text);
                btn.textContent = "Copied";
                btn.classList.add("done");
            } catch (e) {
                btn.textContent = "Select and copy";
            }
            setTimeout(() => { btn.textContent = "Copy"; btn.classList.remove("done"); }, 1800);
        });
    });

    // ---------- FAQ search
    const faqSearch = $("#faq-search");
    if (faqSearch) {
        const items = $$(".faq details");
        const none = $(".no-results");
        faqSearch.addEventListener("input", () => {
            const q = faqSearch.value.trim().toLowerCase();
            let shown = 0;
            items.forEach(d => {
                const hit = !q || d.textContent.toLowerCase().includes(q);
                d.hidden = !hit;
                if (hit) shown++;
                if (q && hit) d.open = true;
            });
            if (none) none.hidden = shown > 0;
        });
    }

    // ---------- forms (feedback, contact, beta, waitlist) post to the feedback server
    const api = (S.apiBase || "").replace(/\/$/, "");
    const bases = { licence: (S.licenceApi || "").replace(/\/$/, "") };
    const params = new URLSearchParams(location.search);
    $$("form[data-api]").forEach(form => {
        const base = form.dataset.apiBase ? bases[form.dataset.apiBase] : api;
        if (!base) {  // forms not connected yet: say so instead of failing on submit
            $$("input, textarea, select, button", form).forEach(el => { el.disabled = true; });
            const note = $("[data-form-status]", form);
            if (note) {
                note.className = "form-status busy";
                note.textContent = S.supportEmail ? `This form opens soon. Until then, email ${S.supportEmail}.` : "This form opens soon. Check back shortly.";
                note.hidden = false;
            }
            return;
        }
        const status = $("[data-form-status]", form);
        const button = $("button[type=submit]", form);
        const started = $("input[name=started]", form);
        if (started) started.value = String(Date.now());
        // Prefill from links in the app, e.g. feedback.html?version=0.1.0&windows=Windows%2011
        for (const [key, field] of [["version", "app_version"], ["windows", "windows"], ["type", "category"], ["token", "token"]]) {
            const v = params.get(key);
            const el = form.elements[field];
            if (!v || !el) continue;
            if (el instanceof RadioNodeList) { const r = [...el].find(x => x.value === v); if (r) r.checked = true; }
            else el.value = v.slice(0, 100);
        }
        const show = (kind, text) => { if (status) { status.className = "form-status " + kind; status.textContent = text; status.hidden = false; } };
        form.addEventListener("submit", async e => {
            e.preventDefault();
            if (!form.reportValidity()) return;
            const label = button.textContent;
            button.disabled = true;
            button.textContent = "Sending…";
            show("busy", "Sending…");
            try {
                const r = await fetch(`${base}/${form.dataset.api}`, { method: "POST", body: new FormData(form) });
                const data = await r.json().catch(() => null);
                if (!data) throw new Error("offline");
                if (!r.ok || !data.ok) { show("err", data.message || "Something went wrong. Please try again."); return; }
                form.reset();
                if (started) started.value = String(Date.now());
                form.dispatchEvent(new Event("change"));
                show("ok", data.message || "Sent. Thank you!");
            } catch (err) {
                show("err", S.supportEmail
                    ? `The form isn't available right now. Please email ${S.supportEmail} instead.`
                    : "The form isn't available right now. Please try again later.");
            } finally {
                button.disabled = false;
                button.textContent = label;
            }
        });
    });

    // Feedback type switches which fields are shown
    const fb = $("form[data-api=feedback]");
    if (fb) {
        const sync = () => {
            const type = (fb.elements.category && fb.elements.category.value) || "bug";
            $$("[data-for]", fb).forEach(el => { el.hidden = !el.dataset.for.split(" ").includes(type); });
            const msg = $("#fb-message-label", fb);
            if (msg) msg.textContent = { bug: "What went wrong?", idea: "What would you like WiFiDrop to do?", question: "Your question" }[type];
        };
        fb.addEventListener("change", sync);
        sync();
    }

    // ---------- pricing: how many people?
    const people = $("#people");
    if (people) {
        const out = $("#people-out");
        const verdict = $("#people-verdict");
        const plans = { free: $(".plan.free"), pro: $(".plan.pro") };
        let last = null;
        const update = () => {
            const n = Number(people.value);
            out.textContent = n >= 20 ? "20+" : String(n);
            const pick = n <= 5 ? "free" : "pro";
            verdict.textContent = pick === "free"
                ? "WiFiDrop Free covers you, with room to spare."
                : "You'll want WiFiDrop Pro for more than 5 accounts. Free still works for up to 5.";
            if (pick !== last && plans[pick] && !reduceMotion) {
                plans[pick].classList.remove("highlight");
                void plans[pick].offsetWidth;
                plans[pick].classList.add("highlight");
            }
            last = pick;
        };
        people.addEventListener("input", update);
        update();
    }

    // ---------- Buy Pro with Paddle's checkout (only on the pricing page, only when configured).
    // While payments are in test mode the button shows only with ?buytest=1, so visitors can't make test purchases.
    const buy = $("[data-buy]");
    const pay = S.paddle || {};
    if (buy && pay.token && pay.priceId && ((pay.env === "production" && pay.open !== false) || params.has("buytest"))) {
        buy.hidden = false;
        $$('form[data-api=waitlist], [data-waitlist-note]').forEach(el => { el.hidden = true; });
        const soon = $(".plan.pro .soon");
        if (soon) soon.textContent = pay.env === "production" && pay.open !== false ? "Available now" : "Test mode";
        if (pay.price) { const price = $(".plan.pro .price"); if (price) price.innerHTML = `${pay.price} <small>CAD, one-time</small>`; }
        const note = $("[data-buy-note]");
        if (pay.env !== "production" && note) note.textContent = "Test mode: use a Paddle test card. No real money is taken.";
        let ready = null;
        const load = () => ready || (ready = new Promise((resolve, reject) => {
            const tag = document.createElement("script");
            tag.src = "https://cdn.paddle.com/paddle/v2/paddle.js";
            tag.onload = () => {
                if (pay.env !== "production") window.Paddle.Environment.set("sandbox");
                window.Paddle.Initialize({
                    token: pay.token,
                    eventCallback: e => {
                        if (e.name === "checkout.completed" && note) {
                            note.textContent = "Thank you! Your licence is on its way to your email. It usually arrives within a minute.";
                        }
                    },
                });
                resolve(window.Paddle);
            };
            tag.onerror = () => { ready = null; reject(new Error("checkout unavailable")); };
            document.head.appendChild(tag);
        }));
        // Show Pro in the visitor's own currency. Paddle converts the CA$29.99 price and knows the local tax;
        // where prices normally include tax (Europe, UK, Australia...) we show the price with tax. If Paddle
        // can't be reached, the CAD price stays.
        if (pay.env === "production" && pay.open !== false) {
            load()
                .then(paddle => paddle.PricePreview({ items: [{ priceId: pay.priceId, quantity: 1 }] }))
                .then(result => {
                    const data = result.data;
                    const line = data.details.lineItems[0];
                    const price = $(".plan.pro .price");
                    if (!line || !price || data.currencyCode === "CAD") return;
                    const f = line.formattedTotals;
                    const withTax = data.address && data.address.countryCode !== "US" && f.total !== f.subtotal;
                    const small = document.createElement("small");
                    small.textContent = `${data.currencyCode}, one-time${withTax ? ", tax included" : ""}`;
                    price.textContent = `${withTax ? f.total : f.subtotal} `;
                    price.appendChild(small);
                    const note = $("[data-price-note]");
                    if (note) {
                        note.textContent = `That's CA${pay.price} converted to your currency. You'll pay in ${data.currencyCode} at checkout.`;
                        note.hidden = false;
                    }
                })
                .catch(() => {});
        }

        $("[data-buy-btn]").addEventListener("click", async () => {
            try {
                const paddle = await load();
                // Match the site's light/dark theme: the visitor's choice, else their device setting.
                const saved = document.documentElement.getAttribute("data-theme");
                const dark = saved ? saved === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
                paddle.Checkout.open({
                    items: [{ priceId: pay.priceId, quantity: 1 }],
                    settings: {
                        displayMode: "overlay",
                        variant: "one-page",          // email, country and card on one screen
                        theme: dark ? "dark" : "light",
                        locale: document.documentElement.lang.startsWith("fr") ? "fr" : "en",
                        showAddDiscounts: false,      // no discount codes
                        successUrl: new URL("thanks.html", location.href).href,
                    },
                });
            } catch {
                if (note) note.textContent = "The checkout couldn't load. Check your connection or ad blocker, then try again.";
            }
        });
    }
})();
