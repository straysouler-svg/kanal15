"""Оформление группы обсуждения «Канал 15 — обсуждение» и аватар бота.

Порядок работы:
1. Пользователь добавляет бота в группу администратором (pin + change info + delete) и пишет там сообщение.
2. Запуск:  python setup_group.py            # найти группу через getUpdates
           python setup_group.py --chat-id -100...   # или указать группу явно
           python setup_group.py --dry-run   # показать план, ничего не менять

Что делает: находит группу, проверяет права бота, ставит фото группы (avatar_15.png),
записывает описание, отправляет и закрепляет закреп из discussion_group_setup.md
(если закреп бота с тем же текстом уже есть — пропускает), ставит боту аватар
(setMyProfilePhoto, Bot API 7.2+).

Токен читается из bot_token.txt и никогда не печатается.
Только стандартная библиотека. Лог пишется в консоль и autopost.log.
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
LOG = HERE / "autopost.log"
AVATAR = HERE / "avatar_15.png"
SETUP_DOC = HERE / "discussion_group_setup.md"
MSK = timezone(timedelta(hours=3))

# Описание группы — до 255 знаков, в тоне закрепа.
DESCRIPTION = ("Стоянка у кафе для тех, кто слушает «Канал 15» в ETS2. "
               "Эфир общий: один говорит, остальные слушают. Без политики и рекламы. "
               "Про мод спрашивайте, ругайте, хвалите — разработчик читает всё.")

PIN_HEADER = "## 1. Закреп группы"


def log(msg):
    line = f"{datetime.now(MSK):%Y-%m-%d %H:%M:%S} setup_group: {msg}"
    try:
        print(line)
    except Exception:
        pass
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


class TelegramError(Exception):
    def __init__(self, msg, http=None):
        super().__init__(msg)
        self.http = http


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
    except OSError as e:
        raise TelegramError(f"сеть: {e}")
    if not res.get("ok"):
        raise TelegramError(res.get("description", "unknown error"), res.get("_http"))
    return res["result"]


def api_retry(method, fields=None, files=None, attempts=5, pause=3):
    """api с повторами: api.telegram.org из РФ периодически рвёт соединение по SSL."""
    last = None
    for i in range(1, attempts + 1):
        try:
            return api(method, fields, files)
        except TelegramError as e:
            last = e
            log(f"{method}: попытка {i}/{attempts} не удалась ({e})")
            if i < attempts:
                time.sleep(pause)
    raise last


def load_pin_text():
    """Закреп из раздела 1 discussion_group_setup.md — текст как есть, без служебных строк."""
    text = SETUP_DOC.read_text(encoding="utf-8")
    part = text.split(PIN_HEADER, 1)[1].split("\n---", 1)[0]
    lines = []
    started = False
    for ln in part.splitlines():
        s = ln.strip()
        if not started:
            if s.startswith("Добро пожаловать"):
                started = True
            else:
                continue  # хвост заголовка и пустые строки до текста закрепа
        if not s or s.startswith("*("):
            continue
        lines.append(ln.rstrip())
    return "\n".join(lines).strip()


def find_group_chat():
    """Новейший чат типа group/supergroup, где бот состоит (по getUpdates)."""
    best = None
    for u in api_retry("getUpdates", {"timeout": 0, "allowed_updates": ["message"]}):
        m = u.get("message")
        if not m:
            continue
        chat = m.get("chat", {})
        if chat.get("type") in ("group", "supergroup"):
            best = chat  # берём самый новый — getUpdates идёт по возрастанию update_id
    return best


def check_rights(chat_id):
    """Вернуть список отсутствующих прав администратора."""
    me = api_retry("getMe")
    member = api_retry("getChatMember", {"chat_id": chat_id, "user_id": me["id"]})
    if member.get("status") not in ("administrator", "creator"):
        return ["БОТ НЕ АДМИНИСТРАТОР ГРУППЫ"]
    missing = [p for p in ("can_pin_messages", "can_change_info", "can_delete_messages")
               if member.get(p) is False]
    return missing


def pinned_already(chat_id, pin_text):
    """В группе уже закреплено сообщение от бота с таким текстом?"""
    try:
        pinned = api_retry("getChat", {"chat_id": chat_id}).get("pinned_message")
    except (TelegramError, OSError) as e:
        log(f"getChat не удался: {e} — считаем, что закрепа нет")
        return False
    if not pinned or not pinned.get("from", {}).get("is_bot"):
        return False
    return (pinned.get("text") or "").strip() == pin_text.strip()


def main():
    args = [a for a in sys.argv[1:]]
    dry = "--dry-run" in args
    chat_id = None
    if "--chat-id" in args:
        i = args.index("--chat-id")
        chat_id = int(args[i + 1])

    if "--avatar-only" in args:
        # только аватар бота: без getUpdates, без группы, без проверки прав
        return set_bot_avatar(dry)

    if len(DESCRIPTION) > 255:
        log(f"ОШИБКА: описание {len(DESCRIPTION)} знаков > 255")
        return 1

    # 1. найти группу
    if chat_id is None:
        log("ищу группу через getUpdates...")
        chat = find_group_chat()
        if not chat:
            log("группа не найдена. Пользователь: добавь бота в группу и напиши туда любое сообщение, "
                "либо запусти: python setup_group.py --chat-id -100...")
            return 1
        chat_id = chat["id"]
        log(f"найдена группа: {chat.get('title')} (chat_id={chat_id})")
    else:
        title = api_retry("getChat", {"chat_id": chat_id}).get("title")
        log(f"группа задана аргументом: {title} (chat_id={chat_id})")

    # 2. права
    missing = check_rights(chat_id)
    if missing:
        log("не хватает прав: " + ", ".join(missing))
        log("Пользователь: открой группу → Управление группой → Администраторы → @kanal15_publisher_bot → "
            "включи «Закрепление сообщений», «Изменение профиля группы», «Удаление сообщений». "
            "Потом запусти скрипт ещё раз.")
        return 1
    log("права бота в порядке")

    pin_text = load_pin_text()
    log(f"закреп: {len(pin_text)} знаков, первая строка: {pin_text.splitlines()[0][:60]}...")

    # 3. фото группы
    if dry:
        log(f"[dry-run] setChatPhoto: {AVATAR.name}")
    else:
        api_retry("setChatPhoto", {"chat_id": chat_id}, files={"photo": AVATAR})
        log("иконка группы обновлена")

    # 4. описание
    if dry:
        log(f"[dry-run] setChatDescription: {DESCRIPTION[:60]}...")
    else:
        api_retry("setChatDescription", {"chat_id": chat_id, "description": DESCRIPTION})
        log("описание группы обновлено")

    # 5. закреп (идемпотентно)
    if pinned_already(chat_id, pin_text):
        log("закреп уже на месте — шаг пропущен")
    elif dry:
        log("[dry-run] sendMessage + pinChatMessage (закрепа с этим текстом нет)")
    else:
        msg = api_retry("sendMessage", {"chat_id": chat_id, "text": pin_text, "disable_web_page_preview": True})
        api_retry("pinChatMessage", {"chat_id": chat_id, "message_id": msg["message_id"], "disable_notification": False})
        log("закреп отправлен и закреплён")

    # 6. аватар бота
    set_bot_avatar(dry)

    log("готово")
    return 0


def set_bot_avatar(dry):
    """setMyProfilePhoto (Bot API 7.2+): photo — InputProfilePhotoStatic как JSON,
    файл — multipart-вложение со ссылкой attach://."""
    if dry:
        log(f"[dry-run] setMyProfilePhoto: {AVATAR.name} (photo={{'type':'static','photo':'attach://avatar'}})")
        return 0
    try:
        api_retry("setMyProfilePhoto",
                  fields={"photo": json.dumps({"type": "static", "photo": "attach://avatar"})},
                  files={"avatar": AVATAR})
        log("аватар бота обновлён")
    except TelegramError as e:
        log(f"setMyProfilePhoto не удался ({e}). Запрос корректен по Bot API 7.2+ — вероятно, метод ещё "
            "не включён на сервере. Тогда аватар бота меняется вручную: @BotFather → /mybots → "
            "выбрать бота → Edit Bot → Edit Botpic, файл {AVATAR}.".format(AVATAR=AVATAR))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
