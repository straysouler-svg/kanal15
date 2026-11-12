"""Постинг в сообщество VK «Канал 15» (текст, фото, видео).
Секреты: promo/vk/token.txt (ключ сообщества) и promo/vk/group_id.txt — НЕ в git.

  python post_vk.py "Текст поста"
  python post_vk.py "Текст" --photo cover.jpg
  python post_vk.py "Текст" --video short.mp4 --video-title "Название клипа"
"""
import argparse
import json
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
TOKEN_F = HERE / "token.txt"
GROUP_F = HERE / "group_id.txt"
API = "https://api.vk.com/method/"
V = "5.199"


def creds():
    if not TOKEN_F.exists() or not GROUP_F.exists():
        sys.exit(f"нет {TOKEN_F} или {GROUP_F} — см. Настройка VK.md")
    return TOKEN_F.read_text().strip(), int(GROUP_F.read_text().strip())


def call(method, token, **params):
    r = requests.post(API + method, data={**params, "access_token": token, "v": V}, timeout=60)
    d = r.json()
    if "error" in d:
        e = d["error"]
        sys.exit(f"VK {method}: ошибка {e['error_code']}: {e['error_msg']}")
    return d["response"]


def upload_photo(token, gid, path):
    srv = call("photos.getWallUploadServer", token, group_id=gid)
    up = requests.post(srv["upload_url"], files={"photo": open(path, "rb")}, timeout=300).json()
    saved = call("photos.saveWallPhoto", token, group_id=gid,
                 photo=up["photo"], server=up["server"], hash=up["hash"])
    p = saved[0]
    return f"photo{p['owner_id']}_{p['id']}"


def upload_video(token, path, title):
    srv = call("video.save", token, name=title, wallpost=0, is_private=0)
    requests.post(srv["upload_url"], files={"video_file": open(path, "rb")}, timeout=3600)
    return f"video{srv['owner_id']}_{srv['video_id']}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("text")
    p.add_argument("--photo")
    p.add_argument("--video")
    p.add_argument("--video-title", default="")
    a = p.parse_args()

    token, gid = creds()
    att = []
    if a.photo:
        att.append(upload_photo(token, gid, a.photo))
    if a.video:
        att.append(upload_video(token, a.video, a.video_title or Path(a.video).stem))
    resp = call("wall.post", token, owner_id=-gid, from_group=1,
                message=a.text, attachments=",".join(att))
    print(json.dumps({"post_id": resp["post_id"],
                      "url": f"https://vk.com/wall-{gid}_{resp['post_id']}"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
