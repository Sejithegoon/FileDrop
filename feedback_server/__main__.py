"""Run the feedback server:  python -m feedback_server [--host 127.0.0.1] [--port 8095] [--site site]"""

import argparse
import logging
import sys
from pathlib import Path

import uvicorn

from .app import create_app
from .config import from_env


def main() -> int:
    p = argparse.ArgumentParser(prog="feedback_server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8095)
    p.add_argument("--site", help="also serve the static website from this folder")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = from_env()
    if args.site:
        config.site_dir = Path(args.site)
    if not config.admin_password:
        logging.warning("FEEDBACK_ADMIN_PASSWORD is not set: the admin page will refuse every login.")
    uvicorn.run(create_app(config), host=args.host, port=args.port, proxy_headers=config.trust_proxy,
                forwarded_allow_ips="127.0.0.1" if config.trust_proxy else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
