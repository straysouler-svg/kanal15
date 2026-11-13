"""OAuth TikTok (песочница): обмен code -> access/refresh token и продление.
Секреты: client_key.txt / client_secret.txt / token.txt / refresh_token.txt — НЕ в git.

  python auth_tiktok.py exchange "<полный URL редиректа с ?code=...>"
  python auth_tiktok.py refresh
"""
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

HERE = Path(__file__).resolve().parent
REDIRECT_URI = "https://github.com/straysouler-svg/kanal15"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def cred(name):
    return (HERE / name).read_text().strip()


def save(d):
    (HERE / "token.txt").write_text(d["access_token"] + "\n")
    (HERE / "refresh_token.txt").write_text(d["refresh_token"] + "\n")
    print(json.dumps({k: d.get(k) for k in ("open_id", "scope", "expires_in",
                                            "refresh_expires_in")}, ensure_ascii=False))


def post(data):
    r = requests.post(TOKEN_URL,
                      headers={"Content-Type": "application/x-www-form-urlencoded"},
                      data=data, timeout=60)
    d = r.json()
    if "access_token" not in d:
        sys.exit(f"TikTok oauth: {json.dumps(d, ensure_ascii=False)}")
    save(d)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "exchange":
        code = parse_qs(urlparse(sys.argv[2]).query).get("code", [None])[0]
        if not code:
            sys.exit("в URL нет ?code=")
        post({"client_key": cred("client_key.txt"),
              "client_secret": cred("client_secret.txt"),
              "code": code, "grant_type": "authorization_code",
              "redirect_uri": REDIRECT_URI})
    elif sys.argv[1] == "refresh":
        post({"client_key": cred("client_key.txt"),
              "client_secret": cred("client_secret.txt"),
              "grant_type": "refresh_token",
              "refresh_token": cred("refresh_token.txt")})
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
