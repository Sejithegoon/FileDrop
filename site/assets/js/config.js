// Site settings. Edit these, then run build/publish-site.ps1. Pages show sensible
// "coming soon" text for anything left empty, so nothing breaks before launch.
window.SITE = {
    version: "0.1.2",
    releaseDate: "2026-10-18",

    // Link to the installer (for example a GitHub Release asset or an R2 bucket file).
    downloadUrl: "https://github.com/Sejithegoon/filedrop-website/releases/download/v0.1.0-beta/WiFiDrop-Setup-0.1.2.exe",
    // From build/build.ps1 output: "SHA-256: ..."
    sha256: "B9A02BBDDB4915543ECC5FAA29588A47F82F00220C1EAC862E8522C69E181EA6",
    downloadSize: "24.6 MB",

    // Where people can write to you.
    supportEmail: "filedrop.support@gmail.com",

    // Where the forms are sent (the Supabase "forms" function). Empty = forms show "opens soon".
    apiBase: "https://chpjqelrwlowdiwxfugl.supabase.co/functions/v1/forms",

    // Supabase project URL and publishable key (safe to publish; used only by admin.html to sign in).
    supabaseUrl: "https://chpjqelrwlowdiwxfugl.supabase.co",
    supabaseKey: "sb_publishable_15mUk_xDPw92KhFEg0l7MA_yg-d_jb-",

    // Licence service (re-send page) and Paddle checkout. The client-side token is public by design.
    licenceApi: "https://chpjqelrwlowdiwxfugl.supabase.co/functions/v1/licence",
    paddle: {
        env: "sandbox",   // "production" at launch; until then the Buy button shows only with ?buytest=1
        token: "test_4aa1cd7b4dad71cdabc78bcf640",  // Paddle > My account > Settings > Authentication > Client-side tokens
        priceId: "pri_01m55sj9bqk0j030ysrazcxwta",  // "WiFiDrop Pro" (sandbox)
        price: "$29 CAD", // placeholder, shown on the pricing page
    },
};
