# -*- coding: utf-8 -*-
"""Непрерывный фон кабины (25.11, пилот cab_bed_pilot — по умолчанию ВЫКЛ).

УТВЕРЖДЁННАЯ ПОЛЬЗОВАТЕЛЕМ МОДЕЛЬ (эталон build/listen_kardan_bed_demo6.wav, 6 итераций
прослушек) — «магнитола слышна только под тангентой»:
- Музыка слышна ТОЛЬКО во время передачи (пока играет реплика). В паузах — тишина.
  Рампы по краям 0.08 с, без щелчков.
- Курсор трека НЕПРЕРЫВЕН от реплики к реплике одного актёра и движется даже в паузах
  (магнитола играет всё время; тангенту слышит её только когда играет передача).
  Курсор per-actor: у каждого своя магнитола и свой курсор, не сбрасываются.
- Смена говорящего → его трек с ЕГО сохранённым курсором.
- Бед проходит РАДИО-ЦЕПОЧКУ (микрофон слышит колонку через эфир), один раз при загрузке:
  band(320..3000) -> tanh(drive=1.6)/tanh(1.6) -> band(300..2200, order=2) ->
  отражения кабины v[13мс:] += 0.22v, v[29мс:] += 0.13v.
- Уровень: бед ×0.159 относительно голоса ×0.95 (BED_LEVEL = 0.159/0.95) — ВЫВЕРЕНО
  ПОЛЬЗОВАТЕЛЕМ, не менять без его слова.
- Дорожный эмбиент (Вера, hired, проезжие) — та же модель и та же цепочка.

wet-треки пилотных актёров пересобраны БЕЗ music-экстры (rerender_actor.py --nomusic),
иначе двойная музыка. Интеграция (cb_radio.py): cab_bed.line(actor, dur) из Player.file
после фактического sd.play. Всё за флагом, снаружи try/except: фон никогда не роняет эфир.
"""
import sys
import threading
import time
from pathlib import Path

import numpy as np

SR = 48000
GATE_RAMP_S = 0.08          # рампы открытия/закрытия «тангенты беда»
BED_LEVEL = 0.159 / 0.95    # бед относительно голоса 0.95 — выверено пользователем, НЕ менять
BLOCK = SR // 20            # 50 мс блоки, как везде в рации
# 26.11 (стрим #16, 21:36 и 21:42 — «Петровне патефон громко»): персональный гейн владельца
# магнитолы поверх BED_LEVEL. Только тем, кого Шеф назвал по имени; остальные — 1.0.
OWNER_GAIN = {"petrovna": 0.6}
# 26.11 (стрим #16, 21:38 — «Петровна, убавь музыку», идея Дмитрия): персональный duck —
# магнитола адресата стихает до DUCK_GAIN. Простая обратимая механика: duck на N минут
# (по умолчанию) или до «вруби обратно» (unduck). Уровень duck ВЫВЕРЕН на глаз от BED_LEVEL,
# при прослушке не ноль (приём живой), но близко.
DUCK_GAIN = 0.12
DUCK_S = 15 * 60            # duck по умолчанию, настоящие секунды

_HERE = Path(__file__).resolve().parent
for _cand in (_HERE / "tools", _HERE, _HERE.parent / "tools"):
    if (_cand / "cab_extras.py").exists() and str(_cand) not in sys.path:
        sys.path.append(str(_cand))
        break

_lock = threading.RLock()
_state = {"disabled": False, "owner": None, "stream": None,
          "cabs": {},                       # owner_key -> {"buf": обработанный зацикленный трек, "pos": курсор}
          "gate_until": 0.0,               # монотоник: до какого момента «тангента беда» нажата
          "duck_until": {},                # 26.11: owner_key -> монотоник, до какого момента duck
          "events": [], "_player": None, "_actors": {}}
_AMBIENT = None


def log(msg):
    try:
        import cb_radio
        cb_radio.log(f"cab_bed: {msg}")
    except Exception:
        print(f"cab_bed: {msg}")


def _event(tag):
    with _lock:
        _state["events"].append((round(time.monotonic(), 3), tag))


def events():
    with _lock:
        return list(_state["events"])


def owner():
    with _lock:
        return _state["owner"]


def cabs():
    """-> {owner: {"pos": курсор, "len": длина трека}} — для стенда (буферы не отдаём)."""
    with _lock:
        return {k: {"pos": v["pos"], "len": len(v["buf"])} for k, v in _state["cabs"].items()}


def _music_raw(style, seed):
    """Сырой трек стиля на владельца (зерно от owner+style) — выбор один раз, не на реплику."""
    import cab_extras
    files = cab_extras._recordings(style)
    if not files:
        return None
    f = files[int(np.random.default_rng(seed).integers(0, len(files)))]
    return cab_extras._load(f)


def _ambient_raw():
    """Сырой дорожный эмбиент: броунов шум в ЛЗ-полосе + гул двигателя 56/63 Гц + шина-шум."""
    global _AMBIENT
    if _AMBIENT is not None:
        return _AMBIENT
    rng = np.random.default_rng(15)
    n = SR * 8
    white = rng.standard_normal(n)
    brown = np.cumsum(white)
    brown = brown - np.linspace(brown[0], brown[-1], n)
    brown /= np.max(np.abs(brown)) + 1e-9
    from scipy.signal import butter, sosfilt
    sos = butter(3, [90, 900], btype="bandpass", fs=SR, output="sos")
    rumble = sosfilt(sos, brown).astype(np.float32) * 0.7
    t = np.arange(n) / SR
    hum = (np.sin(2 * np.pi * 56 * t) * 0.5 + np.sin(2 * np.pi * 112 * t) * 0.25
           + np.sin(2 * np.pi * 63 * t + 0.7) * 0.2).astype(np.float32)
    hiss = sosfilt(butter(2, 5200, btype="highpass", fs=SR, output="sos"),
                   rng.standard_normal(n)).astype(np.float32) * 0.10
    loop = (rumble + hum + hiss) / (np.max(np.abs(rumble + hum + hiss)) + 1e-9) * 0.9
    x = int(0.25 * SR)                          # стык конца с началом
    head, tail = loop[:x].copy(), loop[-x:].copy()
    loop[-x:] = tail * np.linspace(1, 0, x) + head * np.linspace(0, 1, x)
    _AMBIENT = loop.astype(np.float32)
    return _AMBIENT


def radio_chain(x):
    """УТВЕРЖДЁННАЯ цепочка «колонка через тангенту»: band -> tanh(drive) -> band(узже) ->
    отражения кабины. Линейная — применяется один раз при загрузке трека."""
    from scipy.signal import butter, sosfilt
    sos1 = butter(4, [320, 3000], btype="bandpass", fs=SR, output="sos")
    v = sosfilt(sos1, x).astype(np.float32)
    v = np.tanh(v * 1.6) / np.tanh(1.6)
    sos2 = butter(2, [300, 2200], btype="bandpass", fs=SR, output="sos")
    v = sosfilt(sos2, v).astype(np.float32)
    orig = v
    v = orig.copy()
    d13, d29 = int(0.013 * SR), int(0.029 * SR)      # отражения кабины
    v[d13:] += 0.22 * orig[:-d13]
    v[d29:] += 0.13 * orig[:-d29]
    return (v * BED_LEVEL).astype(np.float32)


class _Bed:
    """Постоянный поток беда: текущий курсор зацикленного трека + гейт «тангенты» с рампами."""

    def __init__(self):
        import sounddevice as sd
        self.gain = 0.0                 # 0..1, рампы GATE_RAMP_S к target
        self.target = 0.0
        self.muted = False
        self.stream = sd.OutputStream(channels=1, samplerate=SR, blocksize=BLOCK,
                                      dtype="float32", callback=self._cb)
        self.stream.start()

    def _cb(self, outdata, frames, t, status):
        with _lock:
            st = _state["stream"] is self and _state["owner"]
            cab = _state["cabs"].get(_state["owner"]) if st else None
        if cab is None:
            outdata[:, 0] = 0.0
            return
        chunk = _pump(cab, frames)               # курсор идёт ВСЕГДА (магнитола играет в паузах)
        step = 1.0 / (GATE_RAMP_S * SR / frames)
        self.gain += float(np.clip(self.target - self.gain, -step, step))
        with _lock:
            duck = DUCK_GAIN if time.monotonic() < _state["duck_until"].get(_state["owner"], 0.0) else 1.0
        out = chunk * self.gain * OWNER_GAIN.get(st, 1.0) * duck
        if self.muted:
            out = out * 0.0
        outdata[:, 0] = out


def _pump(cab, frames):
    """Чтение frames от курсора кольцевого трека + продвижение курсора. Колбек и стенд."""
    buf, pos = cab["buf"], cab["pos"]
    chunk = np.empty(frames, np.float32)
    take = min(frames, len(buf) - pos)
    chunk[:take] = buf[pos:pos + take]
    if take < frames:                        # стык по кольцу
        cab["pos"] = frames - take
        chunk[take:] = buf[:frames - take]
    else:
        cab["pos"] = pos + take
    return chunk


def init(player, actors):
    with _lock:
        _state["_player"] = player
        _state["_actors"] = actors or {}


def _spec(actor):
    """-> (kind, style): музыка стиля актёра или дорожный эмбиент. Личные стили (тираж 2)
    привязаны тут: у Веры в кабине нет music-экстры (по канону тишина), её тихие песни —
    отдельный стиль quiet_vera."""
    with _lock:
        actors = _state["_actors"]
    if actor and actor in actors:
        for e in (actors[actor].get("cab") or {}).get("extras") or []:
            if e.get("kind") == "music" and float(e.get("chance", 0) or 0) > 0:
                return "music", e.get("style") or "folk"
        if actor == "vera":                        # 25.11: у Веры тихая личная «магнитола»
            return "music", "quiet_vera"
        return "ambient", None
    return "ambient", None


def _cab_for(owner_key, kind, style):
    """per-actor магнитола: обработанный зацикленный трек + сохранённый курсор.
    Проезжие (foreign): 50/50 — музыкальная кабина из road_all или дорожный эмбиент
    (решение монеткой при создании; тонкая радио-программа — отдельной задачей)."""
    with _lock:
        cabs = _state["cabs"]
        if owner_key not in cabs:
            if owner_key == "foreign":
                import random as _r
                if _r.Random(abs(hash(("coin", owner_key, time.monotonic_ns())))).random() < 0.5:
                    kind, style = "music", "road_all"
                else:
                    kind, style = "ambient", None
            raw = _music_raw(style, abs(hash((owner_key, style))) % 2**32) if kind == "music" \
                else _ambient_raw()
            if raw is None:
                raw = _ambient_raw()
            cabs[owner_key] = {"buf": radio_chain(raw), "pos": 0}
            _event(f"cab:{owner_key}:{kind}")
        return cabs[owner_key]


def line(actor, dur=0.0):
    """Реплика актёра пошла в эфир (Player.file после sd.play): открываем «тангенту беда»
    на длительность реплики. Курсор трека не трогаем — он непрерывен."""
    with _lock:
        if _state["disabled"]:
            return
    owner_key = actor or "foreign"
    kind, style = _spec(actor)
    _cab_for(owner_key, kind, style)            # магнитола создана при первой передаче
    with _lock:
        same = _state["owner"] == owner_key
        _state["owner"] = owner_key
        # 25.11 (указание Шефа «в жесткую, точно в 0 0»): гейт закрывается РОВНО с концом
        # звука реплики — без хвоста +0.10 и без минимума max(dur, 0.3); обрыв — через cut()
        _state["gate_until"] = time.monotonic() + dur
        _event(f"tx:{owner_key}" if same else f"switch:{owner_key}")
        log(f"{'tx' if same else 'switch'} {owner_key} {dur:.1f} с")   # вживую видно, кто держит гейт
        if _state["stream"] is None:
            try:
                _state["stream"] = _Bed()
                _event("stream:on")
            except Exception as e:
                _state["disabled"] = True
                log(f"выключен ({e!r}) — дальше без движкового фона")
                return


def cut():
    """Реплика оборвана досрочно (тангента игрока / пауза игры): закрываем гейт НЕМЕДЛЕННО,
    иначе музыка играет до конца рассчитанной длительности оборванной реплики."""
    with _lock:
        _state["gate_until"] = 0.0


def duck(owner_key, seconds=DUCK_S):
    """26.11 (стрим #16, 21:38): «убавь музыку» — магнитола owner_key стихает до DUCK_GAIN
    на seconds настоящих секунд. Без cab_bed_pilot/стрима — тихий no-op (не роняет эфир)."""
    if not owner_key:
        return
    with _lock:
        _state["duck_until"][owner_key] = time.monotonic() + seconds
    _event(f"duck:{owner_key}:{seconds:.0f}")
    log(f"duck {owner_key} на {seconds / 60:.0f} мин")


def unduck(owner_key):
    """«Вруби обратно» — снять duck раньше времени."""
    if not owner_key:
        return
    with _lock:
        _state["duck_until"].pop(owner_key, None)
    _event(f"unduck:{owner_key}")
    log(f"unduck {owner_key}")


def _watchdog():
    """Гейт по длительности реплик + mute из трея. Демон, живёт с процессом."""
    while True:
        time.sleep(0.03)
        with _lock:
            st = _state
            if st["disabled"] or st["stream"] is None:
                continue
            bed = st["stream"]
            bed.target = 1.0 if time.monotonic() < st["gate_until"] else 0.0
            try:
                import cb_radio
                bed.muted = bool(cb_radio.TRAY_STATE.get("muted"))
            except Exception:
                pass


_wd_started = False


def start_watchdog():
    global _wd_started
    if not _wd_started:
        _wd_started = True
        threading.Thread(target=_watchdog, daemon=True).start()


# ---------------------------------------------------------------- offline-рендер для сверки с эталоном
def render_check(path, plan, actors=None):
    """Офлайн-эквивалент движка для сверки с эталоном: plan = [(actor|None, dur_s), ...]
    с паузами как в демо. Пишет wav; события гейта/курсора — те же, что в движке."""
    import soundfile as sf
    actors = actors or {}
    out, cursor_state = [], {}
    for actor, dur in plan:
        if actor == "pause":                         # тишина в плане демо
            out.append(np.zeros(int(dur * SR), np.float32))
            continue
        key = actor or "foreign"
        if key not in cursor_state:
            kind, style = _spec(actor)
            raw = _music_raw(style, abs(hash((key, style))) % 2**32) if kind == "music" \
                else _ambient_raw()
            if raw is None:
                raw = _ambient_raw()
            cursor_state[key] = {"buf": radio_chain(raw), "pos": 0}
        cab = cursor_state[key]
        buf, pos = cab["buf"], cab["pos"]
        n = int(dur * SR)
        seg = np.empty(n, np.float32)
        take = min(n, len(buf) - pos)
        seg[:take] = buf[pos:pos + take]
        if take < n:
            seg[take:] = buf[:n - take]
            cab["pos"] = n - take
        else:
            cab["pos"] = pos + n
        # рампы 0.08 с по краям «передачи»
        r = int(GATE_RAMP_S * SR)
        seg[:r] *= np.linspace(0, 1, r)
        seg[-r:] *= np.linspace(1, 0, r)
        seg *= OWNER_GAIN.get(key, 1.0)
        out.append(seg)
    mix = np.concatenate(out)
    sf.write(path, mix, SR)
    return path
