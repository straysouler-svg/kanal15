# -*- coding: utf-8 -*-
"""Заливка видео в раздел «Видео» группы VK БЕЗ поста на стену.
  python upload_vk_video.py file.mp4 "Название" ["Описание"]
video.* требует ПОЛЬЗОВАТЕЛЬСКИЙ токен: promo/vk/user_token.txt (VK ID, живёт 1 ч,
обновление: auth_vkid.py refresh). Ключ сообщества (token.txt) для video.* не подходит.
group_id — как в post_vk.py (promo/vk/group_id.txt)."""
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
API = "https://api.vk.com/method/"
V = "5.199"

def main():
    path, title = Path(sys.argv[1]), sys.argv[2]
    desc = sys.argv[3] if len(sys.argv) > 3 else ""
    token = (HERE / "user_token.txt").read_text().strip()
    r = requests.post(API + "video.save", data={
        "access_token": token, "v": V,
        "name": title, "description": desc,
        "wallpost": 0, "is_private": 0, "group_id": (HERE / "group_id.txt").read_text().strip(),
    }, timeout=60).json()
    if "error" in r:
        sys.exit(f"VK video.save: {r['error']['error_code']}: {r['error']['error_msg']}")
    srv = r["response"]
    up = requests.post(srv["upload_url"], files={"video_file": open(path, "rb")}, timeout=3600)
    print(f"OK video{srv['owner_id']}_{srv['video_id']} <- {path.name} (upload {up.status_code})")

if __name__ == "__main__":
    main()
