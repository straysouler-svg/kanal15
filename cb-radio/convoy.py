"""Онлайн-конвой (гость в эфире) — этап 1: синхронизация двух раций на одной машине, 2026-11-12;
этап 2 (21.11): связь через интернет (проброс порта, БЕЗ VPN — решение пользователя) с
обязательной авторизацией пин-кодом; гость — живой человек: его речь распознаёт faster-whisper
ЛОКАЛЬНО у гостя, в сеть уходит только текст said (звук гостя машину хозяина не покидает).

Решения пользователя 12.11: друг слышит ВОДИТЕЛЕЙ игрока; рация передаёт не звук,
а события (transport.py); приватность — Сорока и личные реплики (only_<build>) в
гостевой канал НЕ идут; дружба гостю не пишется; адресация по имени не
делается — гостю отвечают как игроку.

Хозяин (эта рация, у игрока): шлёт play/stop за каждым звуком водителей (Player.file),
принимает ptt/said гостя; приём включается пунктом меню значка, по умолчанию ВЫКЛ.
  config: guest.port — порт; convoy.bind — адрес bind (по умолчанию 127.0.0.1, этап 1 не меняется);
           convoy.pin — пин для внешних подключений (пустой = localhost-only, как этап 1).
Гость (`cb_radio.py --guest [addr:port]`, отдельная папка со своим config):
тонкий клиент — проигрывает присланное через свой Player.file (своё радиоэффектом,
дистанция приходит в событии), без Operator/Deck/мира; своя тангенту шлёт вверх;
этап 2: микрофон гостя (mic.enabled) распознаёт речь локально (whisper), текст — событием
said вверх; файл guest_say.txt остаётся как fallback.

Таймеры — настоящие секунды (time.monotonic), в именах `_S`.
"""

import json
import time
from pathlib import Path

import transport

GUEST_PORT = 47821          # хозяин слушает здесь
HOST = None                 # transport.Host, пока хозяин принимает гостя
GUEST_LINK = None           # transport.Guest, пока эта рация — гость
GUEST_PTT_DOWN = [False]    # тангента гостя у хозяина: эфир молчит, пока он говорит


def convoy_cfg(cfg):
    c = cfg.get("convoy") or {}
    return {"bind": str(c.get("bind") or "127.0.0.1"),
            "pin": str(c.get("pin") or ""),
            "host": str(c.get("host") or f"127.0.0.1:{GUEST_PORT}")}


def radio_version(root):
    try:
        return str(json.loads((Path(root) / "version.json").read_text(encoding="utf-8")).get("version", "?"))
    except Exception:
        return "?"


def host_start(port, log, cfg=None, on_guest=None):
    """Включить приём гостя (меню значка). Уже включён — ничего. bind/pin из convoy-конфига."""
    global HOST
    if HOST:
        return True
    cc = convoy_cfg(cfg or {})
    # CONVOY-SEC-1 (ревизия v1.41, стадия A): слабый/дефолтный pin при интернет-bind = открытая дверь.
    # Не роняем старт (хозяин решает), но предупреждаем ЯРКО. Пустой pin при bind 127.0.0.1 — норма (этап 1).
    _weak = {"", "1234", "1111", "0000", "1212", "7777", "5555", "pass", "password", "qwerty",
             "radio", "radio15", "kanal15", "kanal", "convoy", "гость", "пароль", "пин"}
    if cc["pin"].lower() in _weak and cc["bind"] not in ("127.0.0.1", "::1", "localhost", ""):
        log(f"конвой: ВНИМАНИЕ — pin «{cc['pin']}» слабый/дефолтный при внешнем bind {cc['bind']}: "
            "подбор за секунды. Придумай длинный pin в config.json → convoy.pin")
    try:
        HOST = transport.Host(port, bind=cc["bind"], pin=cc["pin"],
                              mhash=transport.audio_manifest_hash(Path(__file__).resolve().parent / "audio"),
                              on_guest=on_guest, on_warn=log)
    except OSError as e:
        log(f"конвой: порт {port} не открылся ({e!r}) — гость не подключится")
        HOST = None
        return False
    log(f"конвой: жду гостя на {cc['bind']}:{port}"
        + (" (только localhost, pin пуст)" if not cc["pin"] else " (интернет, pin задан)"))
    return True


def host_stop(log):
    global HOST
    if HOST:
        HOST.close()
        HOST = None
        log("конвой: приём гостя выключен")


def host_on():
    return HOST is not None


def host_send_play(rel, actor, dist):
    """Вниз: в эфире пошла реплика (rel — путь от audio/, без расширения)."""
    if HOST and HOST.connected():
        ev = {"e": "play", "p": rel}
        if actor:
            ev["a"] = actor
        if dist is not None:
            ev["d"] = float(dist)
        HOST.send(ev)


def host_send_stop():
    if HOST and HOST.connected():
        HOST.send({"e": "stop"})


def host_send_ptt(down):
    """Хозяин нажал/отпустил тангенту — гость глушит свой эфир."""
    if HOST and HOST.connected():
        HOST.send({"e": "ptt", "down": bool(down)})


def host_poll(log):
    """Забрать события от гостя: -> список ("ptt", down) / ("said", текст) / ("bad", сырьё)."""
    out = []
    if not HOST:
        return out
    evs, bad = HOST.poll()
    for b in bad:
        out.append(("bad", b))
    for ev in evs:
        if ev["e"] == "ptt":
            out.append(("ptt", ev["down"]))
        elif ev["e"] == "said":
            out.append(("said", ev["t"]))
        else:
            out.append(("bad", f"гость прислал лишнее: {ev!r}".encode()))
    return out


def guest_skip(rel, actor, variant_of, log, verbose=False):
    """Приватность (решение пользователя 12.11): гость НЕ слышит Сороку и личные
    реплики only_<build>; variant_of -> None (другой вариант обращений) — тоже тишина.
    Возвращает причину пропуска или None. Отсутствующий файл — проверяет caller."""
    if actor == "soroka":
        return "Сорока (личная, в гостевой канал не идёт)"
    if rel and "/only_" in f"/{rel}/":
        return "личная реплика only_<build>"
    try:
        if variant_of(rel) is None:
            return "нет версии для этого варианта обращений"
    except Exception:
        return "путь вне установки"
    return None


def guest_main(radio, addr_port, pin=None):
    """Режим гостя: тонкий клиент эфира хозяина. radio — импортированный cb_radio
    (передаём параметром, чтобы не импортировать тяжёлый модуль на этапе проверки).
    Вызывается из main() по --guest [addr:port] [--pin …] (без аргументов — convoy из config).
    Без игры, мира, дружбы. Этап 2: микрофон гостя распознаёт речь локально (whisper),
    в сеть уходит только текст said — звук гостя машину хозяина не покидает."""
    cfg = radio.load_cfg()
    cc = convoy_cfg(cfg)
    if not addr_port:
        addr_port = cc["host"]
    host, _, port_s = addr_port.rpartition(":")
    host = host or "127.0.0.1"
    port = int(port_s or GUEST_PORT)
    radio.PLAYER.cfg = cfg
    lock = radio.single_instance(cfg["lock_port"])          # noqa: F841 (держится за процесс)
    log = radio.log
    pin = pin if pin is not None else cc["pin"]              # аргумент --pin перекрывает config
    log(f"конвой: режим ГОСТЯ, хозяин {host}:{port}" + (" (pin задан)" if pin else " (БЕЗ pin — хозяин локальный?)"))

    def link(on):
        log(f"конвой: {'гость на линии' if on else 'хозяин отвалился, переподключаюсь'}")

    global GUEST_LINK
    GUEST_LINK = transport.Guest(host, port, pin=pin, version=radio_version(radio.ROOT),
                                 mhash=transport.audio_manifest_hash(radio.AUDIO_ROOT),
                                 path_ok=None, on_link=link, on_warn=log)
    radio.GUEST_HOOK = guest_ptt                            # тангента этой рации шлёт события, не whisper
    ptt = radio.PTT(cfg)
    radio.PLAYER.ptt = ptt
    ears = None
    if (cfg.get("mic") or {}).get("enabled", True):         # этап 2: голос гостя — локальный whisper
        try:
            ears = radio.Ears(cfg)
            ptt.ears = ears
            log(f"конвой: микрофон гостя — {ears.dev_name}"
                + ("" if ears.ok else " (распознавание недоступно — fallback: guest_say.txt)"))
        except Exception as e:
            log(f"конвой: микрофон гостя не поднялся ({e!r}) — fallback: guest_say.txt")
            ears = None
    say_file = radio.ROOT / "guest_say.txt"
    say_seen = say_file.stat().st_mtime if say_file.exists() else 0.0
    log("конвой: готов — говорите тангентой (распознается локально) или пишите фразу в guest_say.txt")
    wait = None                                              # (job, t_release): ждём распознанную фразу гостя
    try:
        while True:
            ptt.poll()
            time.sleep(0.05)
            ptt.poll()
            if radio.QUIT_REQ["why"] or radio.TRAY_STATE.get("quit"):
                log("конвой: выход")
                break
            while ptt.presses:                              # тангента гостя: ptt уже ушёл через GUEST_HOOK
                dur, interrupted, cut, job = ptt.presses.pop(0)
                if job is not None:
                    wait = [job, time.monotonic()]
                elif dur >= 0.6:
                    log(f"тангента (гость) {dur:.1f} с -> без текста (микрофон выключен, fallback: guest_say.txt)")
            if wait and ears:
                job, t_rel = wait
                if job in ears.results:
                    wait = None
                    text = ears.results.pop(job)
                    if text and GUEST_LINK.send({"e": "said", "t": text}):
                        log(f"тангента (гость): «{text[:60]}» -> хозяину")   # разметка «тангента»: _hide_speech скроет
                    elif text:
                        log("конвой: не ушло хозяину (нет связи) — фраза потеряна")
                elif time.monotonic() - t_rel > 9.0:
                    wait = None
                    log("распознавание (гость) не успело — фраза пропущена")
            evs, bad = GUEST_LINK.poll()
            for b in bad:
                log(f"конвой: битое сообщение от хозяина: {b[:80]!r}")
            for ev in evs:
                if ev["e"] == "stop" or (ev["e"] == "ptt" and ev["down"]):
                    radio.sd.stop()                         # хозяин говорит/оборвал — у гостя тишина
                elif ev["e"] == "play":
                    guest_play(radio, ev, log)
            if say_file.exists():
                try:
                    mt = say_file.stat().st_mtime
                except OSError:
                    mt = 0.0
                if mt != say_seen:
                    say_seen = mt
                    text = say_file.read_text(encoding="utf-8", errors="replace").strip()
                    if text and GUEST_LINK.send({"e": "said", "t": text}):
                        log(f"тангента (гость): «{text[:60]}» -> хозяину")   # разметка «тангента»: _hide_speech скроет
                    try:
                        say_file.unlink()
                    except OSError:
                        pass
    finally:
        GUEST_LINK.close()
        radio.GUEST_HOOK = None


def guest_play(radio, ev, log):
    """Одна реплика хозяина у гостя: тот же файл из своей установки, тот же радиоэффект
    по присланной дистанции. Нет файла — тишина и строка в журнале, не ошибка."""
    rel, actor, dist = ev["p"], ev.get("a"), ev.get("d")
    why = guest_skip(rel, actor, radio.variant_of, log)
    if why is None:
        path = radio.snd(radio.AUDIO_ROOT / (rel + ".wav"))
        if not path.exists():
            why = "файла нет в установке гостя"
    if why:
        log(f"конвой: пропуск {rel or '?'} ({actor or '-'}) — {why}")
        return
    radio.PLAYER.guest_dist = dist          # радиоэффект по дистанции хозяина, без своего мира
    try:
        r = radio.PLAYER.file(path, actor)
    finally:
        radio.PLAYER.guest_dist = None
    if r == "ptt":
        log("конвой: гость перебил реплику тангентой (уже отправлено хозяину)")


def guest_ptt(down):
    """Хук тангенты гостя (ставится в radio.GUEST_HOOK): вверх вместо whisper."""
    if GUEST_LINK:
        GUEST_LINK.send({"e": "ptt", "down": down == "down"})
