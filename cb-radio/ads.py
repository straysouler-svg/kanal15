# -*- coding: utf-8 -*-
"""Местная реклама в эфире «Канала 15» (25.11, пилот ads_pilot — по умолчанию ВЫКЛ).

Правила вентиля — ОДИН В ОДИН из build/ads150/sim_ads.py (спека одобрена Испытателем,
build/ads_check/report.md): зона кафе radius_m, цена = близость × свежесть,
порог PRICE_MIN, лимит MAX_PER_HOUR/час, каденс CADENCE_S, мин. пауза MIN_GAP_S,
анти-повтор «выход из зоны + FRESH_OLD_AGE_S», городской мьют CITY_MUTE_M,
на стоянке (скорость ~0) молчит (PARKED_ADS=False). Стенд гоняет ЭТОТ код.

Политика конфликтов (D2, утверждена Штурманом): живой диалог всегда выше — созревшая
реклама встаёт в очередь длиной 1 (очередь занята — отбрасывается); на рекламу актёры
НЕ реагируют: играем напрямую через sounddevice, мимо колоды, дружбы, оверлея и конвоя.
Тангента пользователя глушит эфир выше этого модуля (air_busy к ней относится).

Интеграция (cb_radio.py): ads.init(...) при первом тике; ads.tick(now, px, pz, speed,
driving, air_busy) из главного цикла под флагом ads_pilot. Всё в try/except — реклама
никогда не роняет эфир.
"""
import json
import random
import threading
from pathlib import Path

_here = Path(__file__).resolve().parent
ADS_DIR = _here / "ads"

# --- константы спеки sim_ads.py (время — НАСТОЯЩИЕ секунды; в симе были минуты) ---
RADIUS_M = 25000.0
CITY_MUTE_M = 2000.0
CADENCE_S = (25.0 * 60, 45.0 * 60)
MAX_PER_HOUR = 2
MIN_GAP_S = 20.0 * 60
PRICE_MIN = 0.3
FRESH_NEVER, FRESH_OLD, FRESH_NEW = 1.0, 0.6, 0.15
FRESH_OLD_AGE_S = 2.0 * 3600
PARKED_ADS = False          # на стоянке реклама молчит
PARK_SPEED_M_S = 1.0        # ниже этой скорости — «припаркован»
QUEUE_LEN = 1               # D2: очередь на эфир, пока идёт живой диалог

_lock = threading.RLock()
_state = {"cafes": None, "cities": None, "radius": RADIUS_M, "play_fn": None,
          "played_at": {},        # n -> monotonic последнего звучания
          "inside": set(),        # кафе, в чьей зоне мы сейчас (анти-повтор «выход + 2 ч»)
          "play_log": [],         # monotonic звучаний за последний час
          "next_allowed": 0.0,
          "queued": None,         # D2: одна ждущая реклама (n кафе)
          "_playing": False,      # 27.11: играет напрямую через sd.play (мимо PLAYER) — пауза обрывает
          "events": [], "_inited": False, "disabled": False}


def log(msg):
    try:
        import cb_radio
        cb_radio.log(f"ads: {msg}")
    except Exception:
        print(f"ads: {msg}")


def _event(tag):
    with _lock:
        _state["events"].append(tag)


def events():
    with _lock:
        return list(_state["events"])


def stop():
    """27.11 (стрим #18, 12:14): реклама играет напрямую через sounddevice, мимо PLAYER, поэтому
    гашение эфира на паузе её не доставало. Обрываем сами — как PLAYER.file «прервано (пауза)».
    Вентиль (пороги/каденс) не трогаем — старт по-прежнему только по driving из cb_radio."""
    with _lock:
        playing = _state["_playing"]
        _state["_playing"] = False
    if not playing:
        return
    try:
        import sounddevice as sd
        sd.stop()                     # в момент перехода в паузу PLAYER молчит — обрываем только рекламу
        log("реклама прервана (пауза/меню)")
    except Exception:
        pass


def reset():
    """Для стенда: чистое состояние вентиля."""
    with _lock:
        for k in ("played_at", "inside", "play_log", "events"):
            _state[k] = set() if k == "inside" else ([] if k in ("play_log", "events") else {})
        _state["next_allowed"], _state["queued"] = 0.0, None
        _state["_playing"] = False


def init(cities, play_fn=None):
    """cities — world.cities ({tok: (name, country, x, z)} или dict с x/z)."""
    with _lock:
        if _state["_inited"]:
            return
        data = json.loads((ADS_DIR / "cafes.json").read_text(encoding="utf-8"))
        _state["cafes"] = data["cafes"]
        _state["radius"] = float(data.get("radius_m", RADIUS_M))
        _state["cities"] = cities or {}
        _state["play_fn"] = play_fn or _default_play
        _state["_inited"] = True


def _default_play(path):
    """Реклама мимо колоды: звук напрямую, без дружбы/оверлея/конвоя (D2)."""
    import sounddevice as sd
    import soundfile as sf
    import cb_radio
    player = cb_radio.PLAYER
    vol = 0.0 if cb_radio.TRAY_STATE.get("muted") else float((player.cfg or {}).get("volume", 0.8))
    x, sr = sf.read(path, dtype="float32")
    sd.play(x * vol, sr, device=(player.cfg or {}).get("device"))


def _city_coords():
    out = []
    for c in (_state["cities"] or {}).values():
        try:
            out.append((float(c["x"]), float(c["z"])))
        except (TypeError, KeyError, IndexError):
            out.append((float(c[2]), float(c[3])))     # кортеж (name, country, x, z)
    return out


def tick(now, px, pz, speed_m_s, driving, air_busy):
    """Один тик вентиля (зовётся из главного цикла). -> None; эффект — события/проигрыш.
    Правила — зеркало run() из sim_ads.py: тот же порядок проверок и формулы."""
    with _lock:
        if _state["disabled"] or not _state["_inited"]:
            return
        st = _state
        # стоянка: реклама выключена правилом PARKED_ADS (в симе — тоже самое)
        if not driving or (not PARKED_ADS and speed_m_s < PARK_SPEED_M_S):
            st["inside"] = set()
            return
        cities = _city_coords()
        if cities:
            in_city = min(((cx - px) ** 2 + (cz - pz) ** 2) ** 0.5 for cx, cz in cities) <= CITY_MUTE_M
        else:
            in_city = False
        cand, now_inside = [], set()
        for c in st["cafes"]:
            dc = ((c["x"] - px) ** 2 + (c["z"] - pz) ** 2) ** 0.5
            if dc <= st["radius"]:
                now_inside.add(c["n"])
                prox = 1.0 - 0.5 * (dc / st["radius"])
                last = st["played_at"].get(c["n"])
                if last is None:
                    fresh = FRESH_NEVER
                elif c["n"] not in st["inside"] and now - last > FRESH_OLD_AGE_S:
                    fresh = FRESH_OLD                      # вышли из зоны и 2 ч прошло
                else:
                    fresh = FRESH_NEW
                cand.append((prox * fresh, c["n"], c["ru"], dc))
        st["inside"] = now_inside
        if in_city or not cand:
            return
        cand.sort(key=lambda t: t[0], reverse=True)
        price, n, ru, dc = cand[0]
        if price < PRICE_MIN:
            _event(f"тишина:{n}")
            return
        # D2: живой диалог выше — очередь длиной 1 (занята — отбрасывается)
        if air_busy:
            if st["queued"] is None:
                st["queued"] = (n, ru, dc)
                _event(f"queued:{n}")
            else:
                _event(f"dropped:{n}")
            return
        if st["queued"] is not None:                       # эфир освободился — играем ждущую
            n, ru, dc = st["queued"]
            st["queued"] = None
            _event(f"dequeued:{n}")
        log_hour = [t for t in st["play_log"] if now - t <= 3600.0]
        if now < st["next_allowed"] or len(log_hour) >= MAX_PER_HOUR:
            _event(f"suppressed:{n}")
            return
        path = ADS_DIR / f"{n:03d}.ogg"
        if not path.exists():
            _event(f"missing:{n}")
            return
        try:
            st["play_fn"](path)
        except Exception as e:
            st["disabled"] = True
            log(f"выключен ({e!r}) — дальше без рекламы")
            return
        st["_playing"] = True
        st["play_log"] = log_hour + [now]
        st["played_at"][n] = now
        st["next_allowed"] = now + max(MIN_GAP_S, random.uniform(*CADENCE_S))
        _event(f"ЭФИР:{n}")
        log(f"эфир: местная реклама ({ru}, {dc / 1000:.1f} км, в зоне {len(cand)})")
