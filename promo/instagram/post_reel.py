"""Публикация Reels в Instagram через официальный Meta Graph API.
Секреты: promo/instagram/token.txt (page access token) и promo/instagram/ig_user_id.txt — НЕ в git.

  python post_reel.py short.mp4 --caption "Описание #ets2"

Видео грузится resumable-загрузкой прямо с диска (публичный URL не нужен).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
TOKEN_F = HERE / "token.txt"
USER_F = HERE / "ig_user_id.txt"
GRAPH = "https://graph.facebook.com/v21.0"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--caption", required=True)
    a = p.parse_args()

    if not TOKEN_F.exists() or not USER_F.exists():
        sys.exit(f"нет {TOKEN_F} или {USER_F} — см. Настройка Instagram.md")
    token = TOKEN_F.read_text().strip()
    ig_user = USER_F.read_text().strip()
    f = Path(a.file)
    size = f.stat().st_size

    r = requests.post(f"{GRAPH}/{ig_user}/media",
                      data={"media_type": "REELS", "upload_type": "resumable",
                            "caption": a.caption, "access_token": token}, timeout=60)
    d = r.json()
    if "id" not in d:
        sys.exit(f"IG media: {json.dumps(d, ensure_ascii=False)[:300]}")
    container = d["id"]

    up = requests.post(f"https://rupload.facebook.com/ig-api-upload/v21.0/{container}",
                       headers={"Authorization": f"OAuth {token}", "offset": "0",
                                "file_size": str(size), "Content-Type": "application/octet-stream"},
                       data=open(f, "rb"), timeout=3600)
    if up.status_code != 200:
        sys.exit(f"IG upload: HTTP {up.status_code} {up.text[:200]}")

    for _ in range(30):
        time.sleep(5)
        s = requests.get(f"{GRAPH}/{container}",
                         params={"fields": "status_code", "access_token": token}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
    else:
        sys.exit("IG: обработка видео не завершилась за 2,5 минуты")

    pub = requests.post(f"{GRAPH}/{ig_user}/media_publish",
                        data={"creation_id": container, "access_token": token}, timeout=60).json()
    if "id" not in pub:
        sys.exit(f"IG publish: {json.dumps(pub, ensure_ascii=False)[:300]}")
    print(json.dumps({"media_id": pub["id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
