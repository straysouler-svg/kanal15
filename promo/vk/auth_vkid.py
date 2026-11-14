# -*- coding: utf-8 -*-
"""Получение пользовательского токена VK ID (PKCE flow для Web-приложений).

  python auth_vkid.py url           -> печатает ссылку авторизации
  python auth_vkid.py exchange "<url из адресной строки>"  -> обмен кода на токен
  python auth_vkid.py refresh       -> обновление токена по refresh_token

Токен пишется в promo/vk/user_token.txt (в git не идёт), refresh_token — в vkid_refresh.txt.
Живёт 1 час; видео заливать сразу после получения. Не печатать токен в чат.
Грабля: id.vk.com/oauth2/auth требует СЕРВИСНЫЙ ключ параметром `service_token`
(НЕ client_secret, НЕ Authorization-заголовок — оба дают «missing service token»).
"""
import base64
import hashlib
import json
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

HERE = Path(__file__).resolve().parent
CLIENT_ID_F = HERE / "vkid_client_id.txt"
STATE_F = HERE / "vkid_pkce.json"          # верифаер и state между шагами
TOKEN_F = HERE / "user_token.txt"
REFRESH_F = HERE / "vkid_refresh.json"
REDIRECT = "https://straysouler-svg.github.io/kanal15/"
SCOPE = "video wall groups offline"


def make_url():
    client_id = CLIENT_ID_F.read_text().strip()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(12)
    STATE_F.write_text(json.dumps({"verifier": verifier, "state": state}), encoding="utf-8")
    url = ("https://id.vk.com/authorize?response_type=code"
           f"&client_id={client_id}&redirect_uri={REDIRECT}"
           f"&code_challenge={challenge}&code_challenge_method=S256"
           f"&state={state}&scope={SCOPE.replace(' ', '%20')}")
    print(url)


def exchange(redirected):
    client_id = CLIENT_ID_F.read_text().strip()
    kept = json.loads(STATE_F.read_text(encoding="utf-8"))
    q = parse_qs(urlparse(redirected).query)
    if "code" not in q:
        sys.exit(f"в адресе нет code: {redirected[:120]}")
    code = q["code"][0]
    device_id = q.get("device_id", [""])[0]
    state = q.get("state", [""])[0]
    r = requests.post("https://id.vk.com/oauth2/auth", data={
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": kept["verifier"],
        "client_id": client_id,
        "service_token": (HERE / "vkid_service_key.txt").read_text().strip(),
        "device_id": device_id,
        "state": state,
        "redirect_uri": REDIRECT,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=60).json()
    if "error" in r:
        sys.exit(f"VK ID oauth2/auth: {r.get('error')}: {r.get('error_description')}")
    save_tokens(r)
    exp = r.get("expires_in", 0)
    print(f"OK: токен сохранён в {TOKEN_F.name}, expires_in={exp} с, user_id={r.get('user_id')}")


def save_tokens(r):
    TOKEN_F.write_text(r["access_token"], encoding="utf-8")
    REFRESH_F.write_text(json.dumps({"refresh_token": r.get("refresh_token", ""),
                                     "device_id": r.get("device_id", "")}), encoding="utf-8")


def refresh():
    client_id = CLIENT_ID_F.read_text().strip()
    kept = json.loads(REFRESH_F.read_text(encoding="utf-8"))
    r = requests.post("https://id.vk.com/oauth2/auth", data={
        "grant_type": "refresh_token",
        "refresh_token": kept["refresh_token"],
        "client_id": client_id,
        "service_token": (HERE / "vkid_service_key.txt").read_text().strip(),
        "device_id": kept["device_id"],
        "state": secrets.token_urlsafe(12),
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=60).json()
    if "error" in r:
        sys.exit(f"VK ID refresh: {r.get('error')}: {r.get('error_description')} — заново: auth_vkid.py url")
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
