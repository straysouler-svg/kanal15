# -*- coding: utf-8 -*-
"""Автопубликация шортсов «Канала 15» в группу VK, зеркало очереди YouTube.

Читает ТУ ЖЕ очередь, что ютуб-бот (promo/youtube/queue.json) — расписание
дублируется минута в минуту. Своё состояние ведёт отдельно: state.json здесь
(id -> video_id, url, posted_at), журнал — autopost_vk.log.
За один запуск публикуется НЕ больше одного ролика (как на YouTube).
Каждый пост — video.save с wallpost=1: пост на стене группы, вертикаль VK
сама подхватывает в клипы.

Токен: пользовательский VK ID (user_token.txt), живёт 1 час — перед публикацией
бот обновляет его через auth_vkid.refresh() (нужен vkid_refresh.json; если его
нет или refresh протух — полный цикл: auth_vkid.py url → exchange).

  python autopost_vk.py            # опубликовать то, чьё время наступило
  python autopost_vk.py --list     # что когда выходит / вышло
  python autopost_vk.py --dry-run  # что опубликовал бы прямо сейчас
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

import auth_vkid

HERE = Path(__file__).resolve().parent
YT_QUEUE = HERE.parent / "youtube" / "queue.json"
STATE = HERE / "state.json"
LOG = HERE / "autopost_vk.log"
API = "https://api.vk.com/method/"
V = "5.199"


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    try:
        print(line)
    except Exception:
        pass                      # pythonw: консоли нет, sys.stdout is None
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def fresh_token():
    try:
        auth_vkid.refresh()
    except SystemExit as e:
        if not auth_vkid.TOKEN_F.exists():
            raise RuntimeError(f"нет токена и refresh не сработал: {e}") from e
        log(f"refresh не сработал ({e}), пробую текущий user_token.txt")
    return auth_vkid.TOKEN_F.read_text(encoding="utf-8").strip()


def publish(p, token):
    f = Path(p["file"])
    if not f.is_absolute():
        f = YT_QUEUE.parent / f
    if not f.exists():
        raise FileNotFoundError(f)
    title = p["title"].replace("#shorts", "").strip()
    desc = p.get("description", "")
    group_id = (HERE / "group_id.txt").read_text(encoding="utf-8").strip()
    # video.save с wallpost=1 на стену группы даёт error 15 (Access denied) —
    # поэтому два шага: заливка пользовательским токеном, пост ключом сообщества.
    r = requests.post(API + "video.save", data={
        "access_token": token, "v": V,
        "name": title, "description": desc,
        "wallpost": 0, "is_private": 0, "group_id": group_id,
    }, timeout=60).json()
    if "error" in r:
        raise RuntimeError(f"video.save: {r['error']['error_code']}: {r['error']['error_msg']}")
    srv = r["response"]
    up = requests.post(srv["upload_url"], files={"video_file": open(f, "rb")}, timeout=3600)
    if up.status_code != 200:
        raise RuntimeError(f"upload: HTTP {up.status_code}")
    attach = f"video{srv['owner_id']}_{srv['video_id']}"
    community = (HERE / "token.txt").read_text(encoding="utf-8").strip()
    r = requests.post(API + "wall.post", data={
        "access_token": community, "v": V,
        "owner_id": f"-{group_id}", "from_group": 1,
        "message": f"{title}\n\n{desc}", "attachments": attach,
    }, timeout=60).json()
    if "error" in r:
        raise RuntimeError(f"wall.post: {r['error']['error_code']}: {r['error']['error_msg']} (видео {attach} залито, пост не создан)")
    return f"https://vk.ru/wall-{group_id}_{r['response']['post_id']}"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass                      # pythonw: консоли нет, sys.stdout is None
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    q = load(YT_QUEUE, {"posts": []})
    state = load(STATE, {})
    now = datetime.now()

    if a.list:
        for p in q.get("posts", []):
            st = state.get(p["id"])
            mark = f"вышел {st['posted_at'][:16]} ({st['url']})" if st else (
                "выключен" if not p.get("enabled", True) else "ждёт")
            print(f"{p['when']}  {p['id']:<28} {mark}")
        return

    due = [p for p in q.get("posts", [])
           if p.get("enabled", True) and p["id"] not in state
           and datetime.strptime(p["when"], "%Y-%m-%d %H:%M") <= now]
    if not due:
        if a.dry_run:
            print("сейчас публиковать нечего")
        return
    p = sorted(due, key=lambda x: x["when"])[0]

    if a.dry_run:
        print(f"опубликовал бы: {p['id']} — {p['title']} ({p['file']})")
        return

    try:
        url = publish(p, fresh_token())
    except Exception as e:
        log(f"ОШИБКА {p['id']}: {e}")
        return
    state[p["id"]] = {"url": url, "posted_at": datetime.now().isoformat(timespec="seconds")}
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"опубликован {p['id']}: {url}")


if __name__ == "__main__":
    main()
