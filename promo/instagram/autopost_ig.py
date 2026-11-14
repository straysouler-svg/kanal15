# -*- coding: utf-8 -*-
"""Автопубликация шортсов «Канала 15» в Instagram (Reels), зеркало очереди YouTube.

Читает ТУ ЖЕ очередь, что ютуб-бот (promo/youtube/queue.json) — расписание
дублируется минута в минуту. Своё состояние ведёт отдельно: state.json здесь,
журнал — autopost_ig.log. За один запуск публикуется НЕ больше одного ролика.

rupload resumable-загрузка у Meta нестабильна (ProcessingFailedError даже на
заведомо рабочем файле), поэтому публикация через video_url: файл на время
кладётся в docs/tmp_ig/ этого репо (GitHub Pages), после публикации удаляется.
Токен — системный SUAT (promo/instagram/token.txt), бессрочный.

  python autopost_ig.py            # опубликовать то, чьё время наступило
  python autopost_ig.py --list     # что когда выходит / вышло
  python autopost_ig.py --dry-run  # что опубликовал бы прямо сейчас
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
YT_QUEUE = HERE.parent / "youtube" / "queue.json"
STATE = HERE / "state.json"
LOG = HERE / "autopost_ig.log"
GRAPH = "https://graph.facebook.com/v21.0"
PAGES = "https://straysouler-svg.github.io/kanal15/tmp_ig"


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


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:200]}")


def host_file(src, name):
    """Положить видео в docs/tmp_ig и запушить; вернуть публичный URL."""
    dst = ROOT / "docs" / "tmp_ig" / name
    dst.parent.mkdir(exist_ok=True)
    dst.write_bytes(src.read_bytes())
    git("add", "docs/tmp_ig")
    git("commit", "-q", "-m", f"tmp: хостинг {name} для IG Reels")
    git("push", "-q", "origin", "HEAD")
    url = f"{PAGES}/{name}"
    for _ in range(24):           # Pages раскатывает до ~2 минут
        time.sleep(5)
        if requests.head(url, timeout=30).status_code == 200:
            return url
    raise RuntimeError(f"Pages не поднял {url} за 2 минуты")


def unhost(name):
    git("rm", "-q", f"docs/tmp_ig/{name}")
    git("commit", "-q", "-m", f"tmp: убрал {name} после публикации в IG")
    git("push", "-q", "origin", "HEAD")


def publish(p):
    f = Path(p["file"])
    if not f.is_absolute():
        f = YT_QUEUE.parent / f
    if not f.exists():
        raise FileNotFoundError(f)
    token = (HERE / "token.txt").read_text(encoding="utf-8").strip()
    ig_user = (HERE / "ig_user_id.txt").read_text(encoding="utf-8").strip()
    title = p["title"].replace("#shorts", "").strip()
    caption = f"{title}\n\nКанал 15 — радиоканал дальнобойщиков для Euro Truck Simulator 2. #ets2 #eurotrucksimulator2 #канал15"

    name = f"{p['id']}.mp4"
    url = host_file(f, name)
    try:
        d = requests.post(f"{GRAPH}/{ig_user}/media",
                          data={"media_type": "REELS", "video_url": url,
                                "caption": caption, "access_token": token}, timeout=60).json()
        if "id" not in d:
            raise RuntimeError(f"IG media: {json.dumps(d, ensure_ascii=False)[:300]}")
        container = d["id"]
        for _ in range(60):
            time.sleep(5)
            s = requests.get(f"{GRAPH}/{container}",
                             params={"fields": "status_code", "access_token": token}, timeout=30).json()
            if s.get("status_code") == "FINISHED":
                break
            if s.get("status_code") == "ERROR":
                raise RuntimeError(f"IG processing ERROR: {json.dumps(s, ensure_ascii=False)[:200]}")
        else:
            raise RuntimeError("IG: обработка не завершилась за 5 минут")
        pub = requests.post(f"{GRAPH}/{ig_user}/media_publish",
                            data={"creation_id": container, "access_token": token}, timeout=60).json()
        if "id" not in pub:
            raise RuntimeError(f"IG publish: {json.dumps(pub, ensure_ascii=False)[:300]}")
    finally:
        try:
            unhost(name)
        except Exception as e:
            log(f"не смог убрать {name} из docs: {e}")
    m = requests.get(f"{GRAPH}/{pub['id']}",
                     params={"fields": "permalink", "access_token": token}, timeout=30).json()
    return m.get("permalink", f"media_id {pub['id']}")


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
        url = publish(p)
    except Exception as e:
        log(f"ОШИБКА {p['id']}: {e}")
        return
    state[p["id"]] = {"url": url, "posted_at": datetime.now().isoformat(timespec="seconds")}
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"опубликован {p['id']}: {url}")


if __name__ == "__main__":
    main()
