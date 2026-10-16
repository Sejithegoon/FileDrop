// Site settings. Edit these, commit, and Cloudflare Pages redeploys. Pages show sensible
// "coming soon" text for anything left empty, so nothing breaks before launch.
window.SITE = {
    version: "0.1.0",
    releaseDate: "2026-10-16",

    // Link to the installer (for example a GitHub Release asset or an R2 bucket file).
    downloadUrl: "",
    // From build/build.ps1 output: "SHA-256: ..."
    sha256: "",
    downloadSize: "",

    // Where people can write to you.
    supportEmail: "",

    // Where the forms are sent. Empty = forms show "opens soon" (GitHub Pages before Phase B).
    // "/api" when the site is served by feedback_server/; your Supabase functions URL after Phase B.
    apiBase: "",
};
