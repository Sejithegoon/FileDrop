// Loaded in <head> (not deferred) so the right theme is applied before the page paints.
(function () {
    var root = document.documentElement;
    root.classList.add("js");
    var saved = null;
    try { saved = localStorage.getItem("fd-theme"); } catch (e) { /* storage blocked */ }
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
})();
