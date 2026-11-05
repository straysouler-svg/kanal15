"""Автопостинг в Telegram-канал «Канал 15» по расписанию schedule.json.

Запускается Планировщиком Windows каждые 15 минут (задача «Канал 15 — автопостинг»).
За один запуск публикует не больше одного поста, и не чаще, чем раз в min_gap_hours:
если компьютер был выключен несколько дней, накопившиеся посты выйдут по одному, а не пачкой.

    python autopost.py            # обычный запуск: опубликовать, если пора
    python autopost.py --list     # расписание и что уже вышло
    python autopost.py --dry-run  # показать, что опубликовал бы сейчас, ничего не отправляя
    python autopost.py --check    # проверить бота и права в канале
    python autopost.py --post ID  # опубликовать пост ID немедленно (вне очереди)

Файлы рядом: bot_token.txt (токен), schedule.json (что и когда), state.json (что уже вышло), autopost.log (журнал).
Только стандартная библиотека Python, без установки пакетов.
"""
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOKEN_FILE = HERE / "bot_token.txt"
SCHEDULE = HERE / "schedule.json"
STATE = HERE / "state.json"
LOG = HERE / "autopost.log"
LOCK = HERE / "autopost.lock"
MSK = timezone(timedelta(hours=3))
MAX_ATTEMPTS = 5


def log(msg):
    line = f"{datetime.now(MSK):%Y-%m-%d %H:%M:%S} {msg}"
    try:
        print(line)
    except Exception:
        pass
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_state(state):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE)


def parse_when(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=MSK)


# ---------- Telegram Bot API ----------

def api(method, fields=None, files=None):
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    url = f"https://api.telegram.org/bot{token}/{method}"
    fields = fields or {}
    if files:
        boundary = uuid.uuid4().hex
        body = bytearray()
        for k, v in fields.items():
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n".encode()
            body += str(v).encode("utf-8") + b"\r\n"
        for k, path in files.items():
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            # латинское имя: кириллица в заголовке multipart может сломать загрузку (название трека идёт в title)
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; "
                     f"filename=\"kanal15{path.suffix.lower()}\"\r\nContent-Type: {ctype}\r\n\r\n").encode("ascii")
            body += path.read_bytes() + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=bytes(body),
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        req = urllib.request.Request(url, data=json.dumps(fields).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            res = json.load(e)
        except Exception:
            res = {"ok": False, "description": f"HTTP {e.code}"}
        res["_http"] = e.code
    if not res.get("ok"):
        raise TelegramError(res.get("description", "unknown error"), res.get("_http"))
    return res["result"]


class TelegramError(Exception):
    def __init__(self, msg, http=None):
        super().__init__(msg)
        self.http = http


def resolve(p):
    path = Path(p)
    return path if path.is_absolute() else (HERE / path).resolve()


def publish(post, chat_id):
    kind = post["kind"]
    base = {"chat_id": chat_id}
    cap = post.get("caption")
    if cap:
        base.update(caption=cap, parse_mode="HTML")
    if kind == "text":
        r = api("sendMessage", {"chat_id": chat_id, "text": post["text"], "parse_mode": "HTML",
                                "link_preview_options": {"is_disabled": True}})
    elif kind == "poll":
        r = api("sendPoll", {"chat_id": chat_id, "question": post["question"],
                             "options": [{"text": o} for o in post["options"]],
                             "allows_multiple_answers": post.get("multiple", False)})
    elif kind in ("audio", "voice", "photo", "video", "document"):
        f = resolve(post["file"])
        if not f.exists():
            raise FileNotFoundError(f"нет файла {f}")
        extra = {k: post[k] for k in ("performer", "title") if k in post and kind == "audio"}
        r = api({"audio": "sendAudio", "voice": "sendVoice", "photo": "sendPhoto",
                 "video": "sendVideo", "document": "sendDocument"}[kind], {**base, **extra}, {kind: f})
    else:
        raise ValueError(f"неизвестный kind={kind}")
    return r["message_id"]


# ---------- logic ----------

def due_posts(sched, state, now):
    out = []
    for p in sched["posts"]:
        st = state.get(p["id"], {})
        if st.get("message_id") or st.get("gave_up") or not p.get("enabled", True):
            continue
        if parse_when(p["when"]) <= now:
            out.append(p)
    return sorted(out, key=lambda p: parse_when(p["when"]))


def last_post_time(state):
    times = [datetime.fromisoformat(v["posted_at"]) for v in state.values() if v.get("posted_at")]
    return max(times) if times else None


def run(dry=False, force_id=None):
    sched = load_json(SCHEDULE, {"posts": []})
    state = load_json(STATE, {})
    now = datetime.now(MSK)
    chat_id = sched["chat_id"]

    if force_id:
        todo = [p for p in sched["posts"] if p["id"] == force_id]
        if not todo:
            log(f"нет поста с id {force_id}")
            return 1
    else:
        todo = due_posts(sched, state, now)
        if not todo:
            return 0
        # опоздавший пост (комп был выключен) ночью не выпускаем: только с 09:00 до 22:00
        late = now - parse_when(todo[0]["when"]) > timedelta(minutes=30)
        if late and not (9 <= now.hour < 22):
            if dry:
                print(f"{todo[0]['id']} опаздывает, но сейчас ночь — выйдет после 09:00")
            return 0
        last = last_post_time(state)
        gap = timedelta(hours=sched.get("min_gap_hours", 3))
        if last and now - last < gap:
            if dry:
                print(f"ждём паузу: последний пост {last:%d.%m %H:%M}, следующий не раньше {last + gap:%d.%m %H:%M}")
            return 0

    post = todo[0]
    if dry:
        print(f"опубликовал бы: {post['id']} ({post['kind']}, по плану {post['when']})")
        return 0
    st = state.setdefault(post["id"], {})
    try:
        mid = publish(post, chat_id)
    except (TelegramError, FileNotFoundError, ValueError, OSError) as e:
        st["attempts"] = st.get("attempts", 0) + 1
        st["last_error"] = str(e)
        # 4xx от Telegram (кроме 429 «слишком часто») и отсутствие файла не лечатся повтором
        permanent = isinstance(e, (FileNotFoundError, ValueError)) or (
            isinstance(e, TelegramError) and e.http and 400 <= e.http < 500 and e.http != 429)
        if permanent or st["attempts"] >= MAX_ATTEMPTS:
            st["gave_up"] = True
        save_state(state)
        log(f"ОШИБКА {post['id']}: {e}" + (" — пост отложен, нужна правка" if st.get("gave_up") else " — повторю позже"))
        return 2
    st.update(message_id=mid, posted_at=now.isoformat(timespec="seconds"))
    st.pop("last_error", None)
    save_state(state)
    late = now - parse_when(post["when"])
    log(f"опубликован {post['id']} (сообщение {mid})" + (f", опоздание {late}" if late > timedelta(minutes=30) else ""))
    return 0


def show_list():
    sched = load_json(SCHEDULE, {"posts": []})
    state = load_json(STATE, {})
    for p in sorted(sched["posts"], key=lambda p: parse_when(p["when"])):
        st = state.get(p["id"], {})
        if st.get("message_id"):
            mark = f"вышел {st['posted_at'][:16].replace('T', ' ')}"
        elif st.get("gave_up"):
            mark = f"ОШИБКА: {st.get('last_error')}"
        elif not p.get("enabled", True):
            mark = "выключен"
        else:
            mark = "ждёт"
        print(f"{p['when']}  {p['id']:<24} {p['kind']:<6} {mark}")


def check():
    sched = load_json(SCHEDULE, {})
    me = api("getMe")
    m = api("getChatMember", {"chat_id": sched["chat_id"], "user_id": me["id"]})
    ok = m.get("status") == "administrator" and m.get("can_post_messages")
    print(f"бот @{me['username']}: {m.get('status')}, публиковать {'можно' if ok else 'НЕЛЬЗЯ'}")
    missing = [p["id"] for p in sched["posts"] if p.get("file") and not resolve(p["file"]).exists()]
    print("файлы на месте" if not missing else f"нет файлов у: {', '.join(missing)}")
    return 0 if ok and not missing else 1


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = sys.argv[1:]
    if "--list" in args:
        return show_list()
    if "--check" in args:
        return check()
    # защита от двух одновременных запусков; замок старше 30 минут считается брошенным
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 1800:
        return 0
    LOCK.write_text(str(datetime.now(MSK)), encoding="utf-8")
    try:
        force = args[args.index("--post") + 1] if "--post" in args else None
        return run(dry="--dry-run" in args, force_id=force)
    except Exception as e:  # чтобы планировщик не копил висящие ошибки
        log(f"СБОЙ: {e!r}")
        return 3
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main() or 0)
