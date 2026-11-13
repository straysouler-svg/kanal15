"""Разовая настройка группы VK «Канал 15»: описание, статус, аватар, обложка, закреп.
Секреты: promo/vk/token.txt, promo/vk/group_id.txt — НЕ в git.

  python setup_group.py info      — описание + статус
  python setup_group.py avatar    — аватар из avatar.png
  python setup_group.py cover     — обложка из cover.png
  python setup_group.py pin ID    — закрепить пост
"""
import json
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
API = "https://api.vk.com/method/"
V = "5.199"

DESCRIPTION = """«Канал 15» — программа-компаньон для Euro Truck Simulator 2. Не мод: файлы игры не трогает, ставится рядом и работает.

В эфире — 18 выдуманных водителей. Слышно только зону рации: кто рядом на трассе, того и слышно, кто уехал — тот молчит. Ответить можно голосом в тангенту — обсудить погоду, спросить новости или попросить мигнуть дальним.

Windows. Бесплатно, с открытым кодом. Я делаю её один, по вечерам, и честно признаюсь в факапах прямо здесь.

https://github.com/straysouler-svg/kanal15
https://t.me/kanal15_ets2"""

STATUS = "На связи. Кто в эфире — отзовитесь."


def creds():
    return (HERE / "token.txt").read_text().strip(), int((HERE / "group_id.txt").read_text().strip())


def call(method, token, **params):
    r = requests.post(API + method, data={**params, "access_token": token, "v": V}, timeout=60)
    d = r.json()
    if "error" in d:
        e = d["error"]
        sys.exit(f"VK {method}: ошибка {e['error_code']}: {e['error_msg']}")
    return d["response"]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    token, gid = creds()

    if cmd == "info":
        call("groups.edit", token, group_id=gid, description=DESCRIPTION)
        try:
            call("status.set", token, group_id=gid, text=STATUS)
        except SystemExit as e:
            print(f"status.set пропущен: {e}", file=sys.stderr)
        print(json.dumps({"ok": True}, ensure_ascii=False))

    elif cmd == "avatar":
        srv = call("photos.getOwnerPhotoUploadServer", token, owner_id=-gid)
        up = requests.post(srv["upload_url"], files={"photo": open(HERE / "avatar.png", "rb")},
                           timeout=300).json()
        saved = call("photos.saveOwnerPhoto", token, server=up["server"],
                     hash=up["hash"], photo=up["photo"])
        print(json.dumps({"photo_id": saved.get("id")}, ensure_ascii=False))

    elif cmd == "cover":
        srv = call("photos.getOwnerCoverPhotoUploadServer", token, group_id=gid,
                   crop_x=0, crop_y=0, crop_x2=1590, crop_y2=400)
        up = requests.post(srv["upload_url"], files={"photo": open(HERE / "cover.png", "rb")},
                           timeout=300).json()
        saved = call("photos.saveOwnerCoverPhoto", token, hash=up["hash"], photo=up["photo"])
        print(json.dumps({"ok": bool(saved)}, ensure_ascii=False))

    elif cmd == "pin":
        call("wall.pin", token, owner_id=-gid, post_id=int(sys.argv[2]))
        print(json.dumps({"pinned": int(sys.argv[2])}, ensure_ascii=False))

    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
