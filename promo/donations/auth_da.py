# -*- coding: utf-8 -*-
"""OAuth DonationAlerts: получение и обновление пользовательского токена.

  python auth_da.py url           -> печатает ссылку авторизации
  python auth_da.py exchange "<url из адресной строки>"  -> обмен кода на токен
  python auth_da.py refresh       -> обновление токена по refresh_token

Токен пишется в promo/donations/da_token.txt, refresh_token — в da_refresh.json
(оба в git не идут). Токены НЕ печатать.
"""
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

HERE = Path(__file__).resolve().parent
CLIENT_ID_F = HERE / "da_client_id.txt"
API_KEY_F = HERE / "da_api_key.txt"       # API Key приложения = client_secret
TOKEN_F = HERE / "da_token.txt"
REFRESH_F = HERE / "da_refresh.json"
REDIRECT = "https://straysouler-svg.github.io/kanal15/"
SCOPE = "oauth-user-show oauth-donation-index"
TOKEN_URL = "https://www.donationalerts.com/oauth/token"


def _creds():
    client_id = CLIENT_ID_F.read_text(encoding="utf-8").strip()
    secret = API_KEY_F.read_text(encoding="utf-8").strip()
    if not client_id or not secret:
        sys.exit("не найдены da_client_id.txt / da_api_key.txt рядом со скриптом")
    return client_id, secret


def make_url():
    client_id, _ = _creds()
    url = ("https://www.donationalerts.com/oauth/authorize"
           f"?client_id={client_id}&redirect_uri={REDIRECT}"
           "&response_type=code"
           f"&scope={SCOPE.replace(' ', '%20')}")
    print(url)


def save_tokens(r):
    TOKEN_F.write_text(r["access_token"], encoding="utf-8")
    REFRESH_F.write_text(json.dumps({"refresh_token": r.get("refresh_token", "")},
                                    ensure_ascii=False), encoding="utf-8")


def exchange(redirected):
    client_id, secret = _creds()
    q = parse_qs(urlparse(redirected).query)
    if "code" not in q:
        sys.exit(f"в адресе нет code: {redirected[:120]}")
    r = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": secret,
        "redirect_uri": REDIRECT,
        "code": q["code"][0],
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=60).json()
    if "error" in r:
        sys.exit(f"DA oauth/token: {r.get('error')}: {r.get('error_description')}")
    save_tokens(r)
    print(f"OK: токен сохранён в {TOKEN_F.name}, expires_in={r.get('expires_in', 0)} с")


def refresh():
    client_id, secret = _creds()
    if not REFRESH_F.exists():
        sys.exit(f"нет {REFRESH_F.name} — сначала: auth_da.py url, затем exchange")
    kept = json.loads(REFRESH_F.read_text(encoding="utf-8"))
    r = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": secret,
        "refresh_token": kept["refresh_token"],
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=60).json()
    if "error" in r:
        sys.exit(f"DA refresh: {r.get('error')}: {r.get('error_description')} — заново: auth_da.py url")
    save_tokens(r)
    print(f"OK: токен обновлён, expires_in={r.get('expires_in', 0)} с")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "url":
        make_url()
    elif len(sys.argv) >= 3 and sys.argv[1] == "exchange":
        exchange(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "refresh":
        refresh()
    else:
        sys.exit(__doc__)
