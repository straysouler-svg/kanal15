"""Обмен OAuth-кода (Facebook Login for Business, unified login) на access token.

  python exchange_code.py "<полный URL редиректа с ?code=...>"

Результат: токен пишется в promo/instagram/token.txt.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

HERE = Path(__file__).resolve().parent
TOKEN_F = HERE / "token.txt"
REDIRECT = "https://straysouler-svg.github.io/kanal15/"
GRAPH = "https://graph.facebook.com/v21.0"


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: exchange_code.py <url_с_code>")
    q = parse_qs(urlparse(sys.argv[1]).query)
    code = q.get("code", [None])[0]
    if not code:
        sys.exit("в URL нет code=")
    app_id = (HERE / "app_id.txt").read_text().strip()
    secret = (HERE / "app_secret.txt").read_text().strip()

    r = requests.get(f"{GRAPH}/oauth/access_token",
                     params={"client_id": app_id, "client_secret": secret,
                             "redirect_uri": REDIRECT, "code": code}, timeout=30)
    d = r.json()
    if "access_token" not in d:
        sys.exit("token exchange: " + json.dumps(d, ensure_ascii=False)[:300])
    TOKEN_F.write_text(d["access_token"], encoding="utf-8")
    exp = d.get("expires_in")
    print(f"OK: токен сохранён, expires_in={exp}")


if __name__ == "__main__":
    main()
