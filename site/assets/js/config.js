// Site settings. Edit these, then run build/publish-site.ps1. Pages show sensible
// "coming soon" text for anything left empty, so nothing breaks before launch.
window.SITE = {
    version: "0.1.3",
    releaseDate: "2026-10-18",

    // Link to the installer (for example a GitHub Release asset or an R2 bucket file).
    downloadUrl: "https://github.com/Sejithegoon/filedrop-website/releases/download/v0.1.0-beta/WiFiDrop-Setup-0.1.3.exe",
    // From build/build.ps1 output: "SHA-256: ..."
    sha256: "1C54029CDFB98CF4B84044503D9B3CD8A3528BA1574CA33574AC69E05A6DF870",
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
        env: "production",  // "sandbox" shows the Buy button only with ?buytest=1 (test mode)
        token: "live_bcdab359084678e2a31e33e7653",  // Paddle (live) > My account > Settings > Authentication > Client-side tokens
        priceId: "pri_01m572yyf9zm0vznbej6ahh9xs",  // "WiFiDrop Pro" $29.99 CAD (live). Sandbox: pri_01m55sj9bqk0j030ysrazcxwta / test_4aa1cd7b4dad71cdabc78bcf640
        price: "$29.99", // shown on the Pro card when checkout is on
    },
};
