"""Транспорт событий «онлайн-конвоя» (гость в эфире), 2026-11-12.

Сменная деталь: рации обмениваются СОБЫТИЯМИ (кто, какая фраза, расстояние),
не звуком. Эта реализация — TCP на 127.0.0.1 (этап 1: две рации на одной машине);
позже за этим же интерфейсом встанет Steam (этап 2).

События (JSON, одна строка = одно событие):
  вниз (хозяин -> гость): {"e":"play","p":"level3/mikhalych/012","a":"mikhalych","d":0.35}
                          {"e":"stop"}                     реплика оборвана (тангента/пауза)
                          {"e":"ptt","down":true}          хозяин нажал тангенту — гость глушит эфир
  вверх (гость -> хозяин): {"e":"ptt","down":false}
                          {"e":"said","t":"кто в эфире?"}  фраза гостя (этап 1: отладочный ввод)

Безопасность (даже для localhost): только 127.0.0.1, путь play — только
относительный, без ".." и без абсолютных путей, белый список расширений,
размер сообщения ограничен MAX_MSG_BYTES, битое сообщение — в список bad для
журнала, соединение и рация живут дальше. Никакого eval/exec — только json.
Логики эфира здесь нет: модуль шлёт и принимает события, решения принимает cb_radio.
"""

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
RECONNECT_S = 3.0              # пауза между попытками переподключения (гость), настоящие секунды


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

    def __init__(self, sock, on_bad):
        self.sock = sock
        self.lock = threading.Lock()
        self.inbox, self.bad = queue.Queue(), on_bad
        self.alive = True
        self._buf = b""
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
    """Хозяин: слушает 127.0.0.1:<port>, принимает одного гостя. send() идёт текущему гостю."""

    def __init__(self, port, path_ok=None, on_guest=None):
        self.port = port
        self.path_ok = path_ok         # для входящих play (хозяин сам ничего не проигрывает по ним — но пусть валидно)
        self.on_guest = on_guest       # callable(connected: bool)
        self.inbox = queue.Queue()
        self.bad = []
        self._conn = None
        self._closed = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", port))
        self.sock.listen(1)
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while not self._closed:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            if self._closed:
                c.close()
                return
            conn = _LineConn(c, self.bad)
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
    """Гость: подключается к хозяину и переподключается сам (раз в RECONNECT_S)."""

    def __init__(self, addr, port, path_ok=None, on_link=None):
        self.addr, self.port, self.path_ok = addr, port, path_ok
        self.on_link = on_link         # callable(connected: bool)
        self.inbox = queue.Queue()
        self.bad = []
        self._conn = None
        self._closed = False
        self._next_try = 0.0
        threading.Thread(target=self._maintain, daemon=True).start()

    def _maintain(self):
        while not self._closed:
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
            self._next_try = time.monotonic() + RECONNECT_S
            try:
                s = socket.create_connection((self.addr, self.port), timeout=3)
            except OSError:
                continue
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
