"""Заливка шортса в TikTok через официальный Content Posting API (v2).
Секреты: promo/tiktok/token.txt (access token) — НЕ в git.

  python upload_tiktok.py short.mp4 --title "Описание #shorts"

ВАЖНО: приложение без ревью TikTok публикует ролики ТОЛЬКО приватно (SELF_ONLY) —
видно лишь владельцу аккаунта. Для публичных постов app должен пройти проверку.
После одобрения приложения поменяй PRIVACY на "PUBLIC_TO_EVERYONE".
"""
import argparse
import json
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
TOKEN_F = HERE / "token.txt"
INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
PRIVACY = "SELF_ONLY"  # до ревью приложения; после — "PUBLIC_TO_EVERYONE"
CHUNK = 10 * 1024 * 1024  # хвост после 8 МБ бывает < 5 МБ — TikTok отвечает "total chunk count is invalid"
MAX_WHOLE = 64 * 1024 * 1024  # до 64 МБ — одним куском: мультичанк у песочницы отклоняется


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--title", required=True)
    a = p.parse_args()

    if not TOKEN_F.exists():
        sys.exit(f"нет {TOKEN_F} — см. Настройка TikTok.md")
    token = TOKEN_F.read_text().strip()
    f = Path(a.file)
    size = f.stat().st_size
    chunk = size if size <= MAX_WHOLE else CHUNK

    init = requests.post(INIT_URL,
                         headers={"Authorization": f"Bearer {token}",
                                  "Content-Type": "application/json; charset=UTF-8"},
                         json={"post_info": {"title": a.title, "privacy_level": PRIVACY},
                               "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                               "chunk_size": chunk,
                                               "total_chunk_count": (size + chunk - 1) // chunk}},
                         timeout=60)
    d = init.json()
    if d.get("error", {}).get("code") not in (None, "ok"):
        sys.exit(f"TikTok init: {json.dumps(d['error'], ensure_ascii=False)}")
    upload_url, publish_id = d["data"]["upload_url"], d["data"]["publish_id"]

    with open(f, "rb") as fh:
        sent = 0
        while True:
            data = fh.read(chunk)
            if not data:
                break
            r = requests.put(upload_url,
                             headers={"Content-Type": "video/mp4", "Content-Length": str(len(data)),
                                      "Content-Range": f"bytes {sent}-{sent + len(data) - 1}/{size}"},
                             data=data, timeout=600)
            if r.status_code not in (200, 201):
                sys.exit(f"TikTok upload: HTTP {r.status_code} {r.text[:200]}")
            sent += len(data)
            print(f"залито {int(sent / size * 100)}%")
    print(json.dumps({"publish_id": publish_id, "privacy": PRIVACY}, ensure_ascii=False))


if __name__ == "__main__":
    main()
