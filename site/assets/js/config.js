// Site settings. Edit these, then run build/publish-site.ps1. Pages show sensible
// "coming soon" text for anything left empty, so nothing breaks before launch.
window.SITE = {
    version: "0.1.5",
    releaseDate: "2026-10-19",

    // Link to the installer (for example a GitHub Release asset or an R2 bucket file).
    downloadUrl: "https://github.com/Sejithegoon/filedrop-website/releases/download/v0.1.0-beta/WiFiDrop-Setup-0.1.5.exe",
    // From build/build.ps1 output: "SHA-256: ..."
    sha256: "7B9406C4560696A6BDE735DE64C99863245D0B1C985BACC3ECF8AAC71BD248AC",
    downloadSize: "24.6 MB",

    // Where people can write to you.
    supportEmail: "support@wifidrop.ca",

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
        open: true,        // true = everyone sees the Buy button; false = only with ?buytest=1
    },
};
