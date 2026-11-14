"""Публикация Reels по публичному video_url (обход rupload).

  python post_reel_url.py <url> --caption "..."
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
    p.add_argument("url")
    p.add_argument("--caption", required=True)
    a = p.parse_args()

    token = TOKEN_F.read_text().strip()
    ig_user = USER_F.read_text().strip()

    d = requests.post(f"{GRAPH}/{ig_user}/media",
                      data={"media_type": "REELS", "video_url": a.url,
                            "caption": a.caption, "access_token": token}, timeout=60).json()
    if "id" not in d:
        sys.exit(f"IG media: {json.dumps(d, ensure_ascii=False)[:300]}")
    container = d["id"]

    for _ in range(60):
        time.sleep(5)
        s = requests.get(f"{GRAPH}/{container}",
                         params={"fields": "status_code", "access_token": token}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            sys.exit(f"IG processing ERROR: {json.dumps(s, ensure_ascii=False)[:300]}")
    else:
        sys.exit("IG: обработка видео не завершилась за 5 минут")

    pub = requests.post(f"{GRAPH}/{ig_user}/media_publish",
                        data={"creation_id": container, "access_token": token}, timeout=60).json()
    if "id" not in pub:
        sys.exit(f"IG publish: {json.dumps(pub, ensure_ascii=False)[:300]}")
    print(json.dumps({"media_id": pub["id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
