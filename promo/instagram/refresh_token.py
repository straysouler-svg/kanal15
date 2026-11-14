"""Продление токена — НЕ НУЖНО: наш токен системный (SUAT, expires_at=0, бессрочный).
Файл оставлен как памятка. Проверка валидности:

  python refresh_token.py check
"""
import json
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
TOKEN_F = HERE / "token.txt"
GRAPH = "https://graph.facebook.com/v21.0"


def main():
    if len(sys.argv) != 2 or sys.argv[1] != "check":
        sys.exit("SUAT не требует продления. usage: refresh_token.py check")
    token = TOKEN_F.read_text().strip()
    app_id = (HERE / "app_id.txt").read_text().strip()
    secret = (HERE / "app_secret.txt").read_text().strip()
    d = requests.get(f"{GRAPH}/debug_token",
                     params={"input_token": token,
                             "access_token": f"{app_id}|{secret}"}, timeout=30).json()
    data = d.get("data", {})
    print(json.dumps({"is_valid": data.get("is_valid"),
                      "type": data.get("type"),
                      "expires_at": data.get("expires_at"),
                      "scopes": data.get("scopes")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
