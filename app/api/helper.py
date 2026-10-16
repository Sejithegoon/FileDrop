"""Plain-HTTP help page, served next to the HTTPS server.

Someone who types just the PC's address (http://192.168.1.20) lands here
instead of a browser error. The page explains the one-time certificate
warning and links to the secure address. It never shows or accepts data.
"""

from __future__ import annotations

import html

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#000000"><title>FileDrop</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: #000; color: #e8eefc; font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
       min-height: 100vh; display: grid; place-items: center; padding: 20px; }}
.card {{ width: min(460px, 100%); background: #0a0d14; border: 1px solid #1c2438; border-radius: 16px; padding: 24px; }}
.brand {{ font-weight: 900; letter-spacing: .06em; font-size: 22px; margin-bottom: 14px; }}
h1 {{ font-size: 20px; margin-bottom: 8px; }}
p, li {{ color: #8a96b0; font-size: 15px; }}
ol {{ margin: 14px 0 18px 20px; display: grid; gap: 8px; }}
b {{ color: #e8eefc; }}
a.btn {{ display: block; text-align: center; padding: 15px; border-radius: 12px; background: #2f7bff; color: #fff;
        font-weight: 700; text-decoration: none; font-size: 17px; }}
code {{ color: #5c9bff; word-break: break-all; }}
</style></head><body><main class="card">
<div class="brand">FILEDROP</div>
<h1>Open FileDrop securely</h1>
<p>FileDrop uses an encrypted connection. The first time, your browser warns that the connection
isn't private, because this computer made its own certificate. That's expected.</p>
<ol>
<li><b>iPhone:</b> tap <b>Show Details</b>, then <b>visit this website</b>.</li>
<li><b>Android:</b> tap <b>Advanced</b>, then <b>Proceed</b>.</li>
<li><b>Computer:</b> choose <b>Advanced</b>, then <b>Continue</b>.</li>
</ol>
<a class="btn" href="{url}">Continue to FileDrop</a>
<p style="margin-top:14px">Secure address: <code>{url}</code></p>
</main></body></html>"""


def create_helper_app(secure_url: str) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    page = PAGE.format(url=html.escape(secure_url, quote=True))

    @app.get("/{path:path}", response_class=HTMLResponse)
    def help_page(path: str = ""):
        return HTMLResponse(page, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    return app
