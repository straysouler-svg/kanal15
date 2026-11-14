"""Автопубликация шортсов «Канала 15» на YouTube по расписанию.

Очередь — queue.json рядом со скриптом:
{
  "posts": [
    {"id": "professor_obida", "when": "2026-11-14 13:00", "file": "../shorts/final_2026-11-09/shorts_professor_obida.mp4",
     "title": "… #shorts", "description": "…", "tags": "ets2,канал 15", "privacy": "public", "enabled": true}
  ]
}
Опубликованное пишется в state.json (id -> video_id, url, posted_at), журнал — autopost_yt.log.
За один запуск публикуется НЕ больше одного ролика (защита от пачек после простоя).
Квота YouTube: загрузка = 1600 ед., дневной лимит 10000 — ~6 роликов в день максимум.

  python autopost_yt.py            # опубликовать то, чьё время наступило
  python autopost_yt.py --list     # что когда выходит / вышло
  python autopost_yt.py --dry-run  # что опубликовал бы прямо сейчас
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from upload_short import youtube  # тот же токен и OAuth

HERE = Path(__file__).resolve().parent
QUEUE = HERE / "queue.json"
STATE = HERE / "state.json"
LOG = HERE / "autopost_yt.log"


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


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass                      # pythonw: консоли нет, sys.stdout is None
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    q = load(QUEUE, {"posts": []})
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

    f = Path(p["file"])
    if not f.is_absolute():
        f = HERE / f
    if not f.exists():
        log(f"ОШИБКА {p['id']}: нет файла {f}")
        return

    from googleapiclient.http import MediaFileUpload
    yt = youtube()
    body = {
        "snippet": {"title": p["title"], "description": p.get("description", ""),
                    "tags": [t.strip() for t in p.get("tags", "").split(",") if t.strip()]},
        "status": {"privacyStatus": p.get("privacy", "public"),
                   "selfDeclaredMadeForKids": False},
    }
    r = yt.videos().insert(part="snippet,status", body=body,
                           media_body=MediaFileUpload(str(f), chunksize=8 * 1024 * 1024, resumable=True)).execute()
    url = f"https://youtube.com/shorts/{r['id']}"
    state[p["id"]] = {"video_id": r["id"], "url": url,
                      "posted_at": datetime.now().isoformat(timespec="seconds")}
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"опубликован {p['id']}: {url}")


if __name__ == "__main__":
    main()
