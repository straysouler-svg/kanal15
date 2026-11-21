"""Транспорт событий «онлайн-конвоя» (гость в эфире), 2026-11-12; этап 2 (21.11).

Сменная деталь: рации обмениваются СОБЫТИЯМИ (кто, какая фраза, расстояние),
не звуком. Этап 1 — TCP на 127.0.0.1 (две рации на одной машине); этап 2 (21.11,
решение пользователя: проброс порта на роутере, БЕЗ VPN) — хозяин слушает на
адресе из конфига (convoy.bind), обязательна авторизация пин-кодом.

События (JSON, одна строка = одно событие):
  вниз (хозяин -> гость): {"e":"play","p":"level3/mikhalych/012","a":"mikhalych","d":0.35}
                          {"e":"stop"}                     реплика оборвана (тангента/пауза)
                          {"e":"ptt","down":true}          хозяин нажал тангенту — гость глушит эфир
  вверх (гость -> хозяин): {"e":"ptt","down":false}
                          {"e":"said","t":"кто в эфире?"}  фраза гостя (этап 2: whisper локально у гостя)

Рукопожатие (первой строкой соединения, в обе стороны):
  гость -> хозяин: {"e":"hello","pin":..., "version":..., "mhash":...}
  хозяин -> гость: {"e":"ok","mhash":...}    пин сошёлся, слушаем
                   {"e":"bye","why":"pin"|"remote"}   отказ (неверный пин / пустой пин + не-localhost)
  mhash — сверка наборов фраз: sha256 по отсортированному списку "относительный путь<TAB>размер"
  для всех .wav/.ogg под audio/ (без хэширования гигабайтов содержимого). Расхождение — НЕ отказ,
  а предупреждение в журнал обеим сторонам (часть реплик у гостя пропадёт).

Безопасность: путь play — только относительный, без ".." и без абсолютных путей,
белый список расширений, размер сообщения ограничен MAX_MSG_BYTES, битое сообщение —
в список bad для журнала, соединение и рация живут дальше. Пустой pin у хозяина =
режим этапа 1: только localhost (не-localhost отклоняется) и первой строкой может
идти не hello, а сразу событие (совместимость со старыми гостями). Никакого
eval/exec — только json. Логики эфира здесь нет: решения принимает cb_radio.
"""

import hashlib
import json
import queue
import socket
import threading
import time
from pathlib import PurePosixPath, PureWindowsPath

MAX_MSG_BYTES = 64 * 1024
MAX_TEXT = 500                 # «said»: фраза длиннее — обрезаем
OK_SUFFIX = (".wav", ".ogg")   # звук в установке рации — только такой
EVENTS = ("play", "stop", "ptt", "said")
HELLO_TIMEOUT_S = 5.0          # таймаут рукопожатия
BACKOFF_MIN_S = 3.0            # переподключение гостя: 3 -> 30 с, настоящие секунды
BACKOFF_MAX_S = 30.0
RECONNECT_S = BACKOFF_MIN_S    # (этап 1) пауза между попытками — теперь растёт до BACKOFF_MAX_S


def _readline(sock, limit=MAX_MSG_BYTES):
    """Одна строка из сокета (для рукопожатия). -> bytes без '\n' или None при обрыве/таймауте/переполнении."""
    buf = b""
    try:
        while b"\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                return None
            buf += chunk
            if len(buf) > limit:
                return None
    except OSError:
        return None
    return buf.split(b"\n", 1)[0]


def _check_hello(ev):
    """hello из сети -> (pin, version, mhash) или BadEvent."""
    if not isinstance(ev, dict) or ev.get("e") != "hello":
        raise BadEvent("первая строка — не hello")
    out = []
    for k in ("pin", "version", "mhash"):
        v = ev.get(k, "")
        if not isinstance(v, str) or len(v) > 128:
            raise BadEvent(f"hello: {k} не строка/огромный")
        out.append(v)
    return out


def audio_manifest_hash(root):
    """mhash: sha256 по отсортированному списку 'относительный путь<TAB>размер' всех .wav/.ogg под root.
    Устойчив к mtime, чувствителен к набору файлов. root — папка audio/."""
    root = PurePosixPath(str(root).replace("\\", "/"))
    lines = []
    try:
        for p in sorted(root.rglob("*")):
            if p.suffix.lower() in OK_SUFFIX and p.is_file():
                lines.append(f"{p.relative_to(root)}\t{p.stat().st_size}")
    except OSError:
        return "-"
    return hashlib.sha256("\n".join(lines).encode("utf-8", "replace")).hexdigest()[:16]


class BadEvent(ValueError):
    """Событие не прошло проверку — причина в тексте исключения."""


def _is_absolute(p):
    return PurePosixPath(p).is_absolute() or PureWindowsPath(p).is_absolute() or \
        bool(PureWindowsPath(p).drive)


def check_path(p, path_ok=None):
    """play-путь: относительный, без "..", без служебных частей, расширение из белого списка
    (или без расширения — ID фразы), и, если передан path_ok, — проходит проверку установки."""
    if not isinstance(p, str) or not p or len(p) > 512:
        raise BadEvent("путь play: пустой или огромный")
    if "\x00" in p or "\n" in p:
        raise BadEvent("путь play: служебные символы")
    if _is_absolute(p):
        raise BadEvent(f"путь play: абсолютный ({p[:40]})")
    parts = PurePosixPath(p.replace("\\", "/")).parts
    if ".." in parts:
        raise BadEvent(f"путь play: есть '..' ({p[:40]})")
    suf = PurePosixPath(p).suffix.lower()
    if suf and suf not in OK_SUFFIX:
        raise BadEvent(f"путь play: чужое расширение ({suf})")
    if path_ok is not None and not path_ok(p):
        raise BadEvent(f"путь play: нет в установке ({p[:40]})")
    return p


def check_event(ev, path_ok=None):
    """Событие из сети -> словарь или BadEvent. Внешний мир не должен уметь слать что попало."""
    if not isinstance(ev, dict):
        raise BadEvent("не словарь")
    e = ev.get("e")
    if e not in EVENTS:
        raise BadEvent(f"неизвестный тип {e!r}")
    if e == "play":
        check_path(ev.get("p"), path_ok)
        if "a" in ev and not isinstance(ev["a"], str):
            raise BadEvent("actor не строка")
        if "d" in ev and not isinstance(ev["d"], (int, float)):
            raise BadEvent("d не число")
    elif e == "ptt":
        if not isinstance(ev.get("down"), bool):
            raise BadEvent("down не bool")
    elif e == "said":
        t = ev.get("t")
        if not isinstance(t, str) or not t.strip():
            raise BadEvent("пустой текст said")
        ev = dict(ev, t=t.strip()[:MAX_TEXT])
    return ev


class _LineConn:
    """Одно соединение: приём построчного JSON в потоке, отправка с локом. Битые строки —
    в self.bad (их забирает владелец для журнала), соединение при этом живёт."""

    def __init__(self, sock, on_bad, initial=b""):
        self.sock = sock
        self.lock = threading.Lock()
        self.inbox, self.bad = queue.Queue(), on_bad
        self.alive = True
        self._buf = initial
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while self.alive:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                self._buf += chunk
                while b"\n" in self._buf:
                    line, self._buf = self._buf.split(b"\n", 1)
                    self._eat(line)
                if len(self._buf) > MAX_MSG_BYTES:     # строка без конца и длиннее лимита — грубый клиент
                    self.bad.append(self._buf[:80])
                    break
        except OSError:
            pass
        finally:
            self.alive = False

    def _eat(self, line):
        if len(line) > MAX_MSG_BYTES:
            self.bad.append(line[:80])
            return
        try:
            ev = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.bad.append(line[:120])
            return
        try:
            self.inbox.put(check_event(ev, self.path_ok))
        except BadEvent as e:
            self.bad.append(f"{e}: {line[:80]!r}".encode("utf-8", "replace"))

    path_ok = None     # класс-атрибут; экземпляр может переопределить до приёма (хозяин не проверяет пути)

    def send(self, ev):
        data = json.dumps(ev, ensure_ascii=False).encode("utf-8") + b"\n"
        if len(data) > MAX_MSG_BYTES:
            return False
        with self.lock:
            try:
                self.sock.sendall(data)
                return True
            except OSError:
                self.alive = False
                return False

    def close(self):
        self.alive = False
        try:
            self.sock.close()
        except OSError:
            pass


class Host:
    """Хозяин: слушает <bind>:<port>, принимает одного гостя. send() идёт текущему гостю.
    pin непустой = интернет-режим: гость обязан представиться hello с верным пином.
    pin пустой = этап 1: только 127.0.0.1, hello не обязателен (первая строка может быть событием)."""

    def __init__(self, port, bind="127.0.0.1", pin="", mhash="", path_ok=None, on_guest=None, on_warn=None):
        self.port, self.bind = port, bind
        self.pin = pin or ""           # пустой = localhost-only, как этап 1
        self.mhash = mhash or ""
        self.path_ok = path_ok         # для входящих play (хозяин сам ничего не проигрывает по ним — но пусть валидно)
        self.on_guest = on_guest       # callable(connected: bool)
        self.on_warn = on_warn         # callable(строка): отказ пина, расхождение mhash
        self.inbox = queue.Queue()
        self.bad = []
        self._conn = None
        self._closed = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((bind, port))
        self.sock.listen(1)
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while not self._closed:
            try:
                c, addr = self.sock.accept()
            except OSError:
                return
            if self._closed:
                c.close()
                return
            try:
                c.settimeout(HELLO_TIMEOUT_S)
                line = _readline(c)
                if line is None:
                    c.close()
                    continue
                buf = b""
                try:
                    ev0 = json.loads(line.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    ev0 = None
                legacy = False
                if not self.pin:
                    # этап 1: hello не обязателен — первая строка может быть сразу событием (старый гость/тесты)
                    try:
                        pin, _ver, gmhash = _check_hello(ev0)
                    except BadEvent:
                        legacy, pin, gmhash = True, "", ""
                else:
                    try:
                        pin, _ver, gmhash = _check_hello(ev0)
                    except BadEvent as e:
                        self.bad.append(f"рукопожатие: {e}: {line[:60]!r}".encode("utf-8", "replace"))
                        if self.on_warn:
                            self.on_warn(f"конвой: гость отклонён ({e})")
                        c.close()
                        continue
                remote = addr[0] not in ("127.0.0.1", "::1", "localhost")
                try:
                    if remote and not self.pin:
                        raise BadEvent(f"подключение не с localhost при пустом pin ({addr[0]})")
                    if self.pin and pin != self.pin:
                        raise BadEvent(f"неверный pin (с {addr[0]})")
                except BadEvent as e:
                    why = "remote" if "localhost" in str(e) else "pin"
                    try:
                        c.sendall(json.dumps({"e": "bye", "why": why}).encode("utf-8") + b"\n")
                    except OSError:
                        pass
                    self.bad.append(f"рукопожатие: {e}".encode("utf-8", "replace"))
                    if self.on_warn:
                        self.on_warn(f"конвой: гость отклонён ({e})")
                    c.close()
                    continue
                if not legacy:
                    c.sendall(json.dumps({"e": "ok", "mhash": self.mhash}).encode("utf-8") + b"\n")
                    if gmhash and self.mhash and gmhash != self.mhash and self.on_warn:
                        self.on_warn(f"конвой: наборы фраз разошлись (гость {gmhash}, у меня {self.mhash}) — "
                                     f"часть реплик у гостя будет молчать")
                else:
                    buf = line + b"\n"               # первая строка — событие: отдаём в общий парсер
                c.settimeout(None)
            except OSError:
                c.close()
                continue
            conn = _LineConn(c, self.bad, initial=buf)
            conn.path_ok = self.path_ok
            conn.inbox = self.inbox          # события — в общую очередь хозяина
            old = self._conn
            self._conn = conn
            if old:
                old.close()            # новый гость вытесняет старого
            if self.on_guest:
                self.on_guest(True)

    def connected(self):
        c = self._conn
        return bool(c and c.alive)

    def send(self, ev):
        c = self._conn
        if not c or not c.alive:
            return False
        if not c.send(check_event(ev, None)):
            if self.on_guest:
                self.on_guest(False)
            return False
        return True

    def poll(self):
        """Все накопившиеся события и битые строки -> (events, bad_lines)."""
        evs = []
        while True:
            try:
                evs.append(self.inbox.get_nowait())
            except queue.Empty:
                break
        bad = self.bad[:]                # список разделяется с живым соединением: копируем и чистим на месте
        del self.bad[:]
        if self._conn and not self._conn.alive and self.on_guest:
            self.on_guest(False)
        return evs, bad

    def close(self):
        self._closed = True
        if self._conn:
            self._conn.close()
        try:
            self.sock.close()
        except OSError:
            pass


class Guest:
    """Гость: подключается к хозяину с рукопожатием (hello: pin/version/mhash), переподключается сам
    с ростом паузы 3 -> 30 с. Отказ по пину (bye) — не повторяем: пин не исправится сам, в журнал строка."""

    def __init__(self, addr, port, pin="", version="", mhash="", path_ok=None, on_link=None, on_warn=None):
        self.addr, self.port, self.path_ok = addr, port, path_ok
        self.pin, self.version, self.mhash = pin or "", version or "", mhash or ""
        self.on_link = on_link            # callable(connected: bool)
        self.on_warn = on_warn            # callable(строка): отказ, расхождение mhash
        self.inbox = queue.Queue()
        self.bad = []
        self._conn = None
        self._closed = False
        self._next_try = 0.0
        self._backoff = BACKOFF_MIN_S
        self.refused = False              # хозяин отказал по пину — переподключаться бессмысленно
        threading.Thread(target=self._maintain, daemon=True).start()

    def _maintain(self):
        while not self._closed:
            if self.refused:
                return
            c = self._conn
            if c and c.alive:
                time.sleep(0.2)
                continue
            if self._conn:                     # слиняло — сообщим один раз
                self._conn = None
                if self.on_link:
                    self.on_link(False)
            if time.monotonic() < self._next_try:
                time.sleep(0.1)
                continue
            self._next_try = time.monotonic() + self._backoff
            try:
                s = socket.create_connection((self.addr, self.port), timeout=3)
            except OSError:
                self._backoff = min(self._backoff * 2, BACKOFF_MAX_S)
                continue
            try:
                s.settimeout(HELLO_TIMEOUT_S)
                hello = json.dumps({"e": "hello", "pin": self.pin, "version": self.version,
                                    "mhash": self.mhash}, ensure_ascii=False).encode("utf-8") + b"\n"
                s.sendall(hello)
                line = _readline(s)
                if line is None:
                    raise OSError("нет ответа на hello")
                try:
                    ev = json.loads(line.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    raise OSError(f"битый ответ на hello: {line[:60]!r}")
                if ev.get("e") == "bye":
                    self.refused = True
                    why = ev.get("why", "?")
                    if self.on_warn:
                        self.on_warn(f"конвой: хозяин отказал в подключении ({why}) — проверьте pin/ip")
                    if self.on_link:
                        self.on_link(False)
                    s.close()
                    return
                if ev.get("e") != "ok":
                    raise OSError(f"неожиданный ответ на hello: {line[:60]!r}")
                hm = ev.get("mhash", "")
                if hm and self.mhash and hm != self.mhash and self.on_warn:
                    self.on_warn(f"конвой: наборы фраз разошлись (хозяин {hm}, у меня {self.mhash}) — "
                                 f"части реплик у меня не будет")
                s.settimeout(None)
            except OSError as e:
                self._backoff = min(self._backoff * 2, BACKOFF_MAX_S)
                self.bad.append(str(e).encode("utf-8", "replace"))
                try:
                    s.close()
                except OSError:
                    pass
                continue
            self._backoff = BACKOFF_MIN_S      # взошло — пауза сброшена
            conn = _LineConn(s, self.bad)
            conn.path_ok = self.path_ok
            conn.inbox = self.inbox          # события — в общую очередь гостя
            self._conn = conn
            if self.on_link:
                self.on_link(True)

    def connected(self):
        c = self._conn
        return bool(c and c.alive)

    def send(self, ev):
        c = self._conn
        if not c or not c.alive:
            return False
        return c.send(check_event(ev, None))

    def poll(self):
        evs = []
        while True:
            try:
                evs.append(self.inbox.get_nowait())
            except queue.Empty:
                break
        bad = self.bad[:]
        del self.bad[:]
        return evs, bad

    def close(self):
        self._closed = True
        if self._conn:
            self._conn.close()
