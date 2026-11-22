# -*- coding: utf-8 -*-
"""Рантайм DSP-модуль голосов проезжих (22.11, ТЗ Дмитрия: phrases/dsp_module_proezzhie_design_2026-11-22.md).

Обрабатывает УЖЕ готовые wet-файлы на пути воспроизведения — ТОЛЬКО пулы проезжих
(foreign.*, streambot, night_mystic; см. wants()). Наши актёры через модуль НЕ проходят.

Цепочка: «магнитофонная лента» (rate без компенсации питча, базовый режим) -> EQ микрофона
(HP/LP + плавающий резонанс) -> pre-gain + tanh-клиппинг -> пресет дистанции (near/far/flyby
с огибающей шума и LP) -> процедурная обвязка (VOX-обрезка + керчанк, фон кабины из cab.py,
хвост керчанка/роджер-бип). Сэмплы — из audio/fx (керчанки), фон — синтез cab.py.

Архетипы и вероятности — в phrases/dsp_profiles.json (НЕ config.json), ±10% рандома внутри
архетипа. Сид — от события (ключ + счётчик) — воспроизводимость в стенде.

Архитектура под будущее: profiles.json имеет пустой раздел "actor_states" — отдельным флагом
сюда же можно будет завести «состояния» актёров (азарт/усталость/дистанция): process()
принимает profile=... извне, wants() можно расширить. Реализация — по слову Дмитрия.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter, sosfilt

ROOT = Path(__file__).resolve().parent
SR = 16000                    # CB-моно: узкий диапазон, почти не грузит ЦП (ТЗ)
FX = ROOT / "audio" / "fx"
sys.path.insert(0, str(ROOT / "tools"))
import cab  # noqa: E402  чистый numpy/scipy, без torch

_profiles = None
_event = [0]                  # счётчик событий — сид воспроизводим и разнообразен

# пулы проезжих, которые проходят через DSP (пилот voicedsp_pilot)
PREFIXES = ("reactions/foreign/", "reactions/foreign_reply/", "reactions/foreign_warm/",
            "reactions/streambot/", "reactions/night_mystic/")


def profiles():
    global _profiles
    if _profiles is None:
        _profiles = json.loads((ROOT / "phrases" / "dsp_profiles.json").read_text(encoding="utf-8"))
    return _profiles


def wants(rel, cfg=None):
    """Этот rel — из пула проезжих и пилот включён? (дефолт ВЫКЛ — включает Дмитрий)"""
    if not rel or not (cfg or {}).get("voicedsp_pilot"):
        return False
    return any(rel.startswith(p) for p in PREFIXES)


# ---------------------------------------------------------------- фильтры (на 16 кГц)

def _sos(kind, f, order=2):
    return butter(order, f, btype=kind, fs=SR, output="sos")


def _hp(x, f):
    return sosfilt(_sos("highpass", min(f, SR / 2 - 100)), x)


def _lp(x, f):
    return sosfilt(_sos("lowpass", min(f, SR / 2 - 100)), x)


def _reson(x, f, gain_db, q=4.0):
    """Узкий «колокол» пикинг-EQ (характер тангетки). gain_db +/-, Q=4 по ТЗ."""
    if abs(gain_db) < 0.1:
        return x
    a = 10 ** (gain_db / 40)                     # амплитуда от дБ (peak)
    w = 2 * np.pi * min(f, SR / 2 - 200) / SR
    alpha = np.sin(w) / (2 * q)
    cosw = np.cos(w)
    b = [1 + alpha * a, -2 * cosw, 1 - alpha * a]
    a_ = [1 + alpha / a, -2 * cosw, 1 - alpha / a]
    return lfilter(b, a_, x)


def _noise(n, rng):
    """Розово-белый эфирный треск: белый через полосовик + низкий гул."""
    white = rng.standard_normal(n)
    hiss = sosfilt(butter(2, [500, 4000], btype="bandpass", fs=SR, output="sos"), white)
    rumble = sosfilt(_sos("bandpass", [80, 300], 2), rng.standard_normal(n)) * 0.4
    return hiss + rumble


# ---------------------------------------------------------------- обвязка

_kerchunks = None
_roger = None


def _fx_cache():
    global _kerchunks, _roger
    if _kerchunks is None:
        _kerchunks = [sf.read(f, dtype="float32")[0] for f in sorted(FX.glob("kerchunk_*.wav"))]
        _kerchunks = [(x if x.ndim == 1 else x.mean(axis=1)) for x in _kerchunks]
        rp = FX / "ptt_release_roger.wav"
        _roger = sf.read(rp, dtype="float32")[0] if rp.exists() else None
        if _roger is not None and _roger.ndim > 1:
            _roger = _roger.mean(axis=1)


def _to16(x, sr):
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SR:
        from scipy.signal import resample_poly
        g = np.gcd(sr, SR)
        x = resample_poly(x, SR // g, sr // g).astype(np.float32)
    return x


def _cab_bg(n, rng, kind):
    """Фон кабины: синтез cab.py (на его 48 кГц) -> ресемпл в 16 кГц, громкость вызовет код ниже."""
    k48 = int(n * cab.SR / SR)
    if kind == "engine":
        x = cab.engine(k48, rng, rpm=1100 + rng.uniform(-100, 200)) * 10 ** (-16 / 20)
    elif kind == "blinker":
        x = cab.blinker(k48, rng) * 10 ** (-12 / 20)
    elif kind == "road":
        x = cab.road(k48, rng) * 10 ** (-14 / 20)
    else:                                   # wind/тихий свист
        x = cab.wind(k48, rng) * 10 ** (-20 / 20)
    from scipy.signal import resample_poly
    return resample_poly(x, SR, cab.SR).astype(np.float32)[:n]


# ---------------------------------------------------------------- главная цепочка

def process(x, sr, seed_key, profile=None):
    """Один проход: wet-файл -> уникальный голос проезжего. seed_key — строка события
    (напр. rel файла): сид = hash(seed_key) + счётчик -> воспроизводимо в стенде."""
    prof = profile or pick_profile(seed_key)
    rng = np.random.default_rng(prof.pop("_seed"))
    j = lambda v, pct=0.1: v * (1 + rng.uniform(-pct, pct))        # ±10% внутри архетипа
    x = _to16(x, sr)
    n = len(x)

    # 5a. pre-roll: с вероятностью vox_p обрезаем начало (задержка VOX) и вставляем керчанк
    _fx_cache()
    head = np.zeros(0, np.float32)
    if rng.random() < prof.get("vox_p", 0.3):
        cut = int(j(rng.uniform(0.15, 0.30), 0))
        x = x[cut:]
        n = len(x)
        click = _kerchunks[int(rng.integers(0, len(_kerchunks)))]
        click = _to16(click, 48000)
        head = click * j(0.8)
    # 5b. фон кабины (-28...-35 дБ относительно голоса)
    bg = np.zeros(n, np.float32)
    for kind, db in prof.get("bg", []):
        bg = bg + _cab_bg(n, rng, kind) * j(1)
    bg *= 10 ** (j(rng.uniform(-35, -28)) / 20) / (np.std(bg) + 1e-9) * (np.std(x) + 1e-9)
    x = x + bg

    # 1. «магнитофонная лента»: rate без компенсации питча (базовый режим ТЗ)
    rate = j(prof.get("rate", 1.0))
    t = np.arange(int(n / rate)) * rate
    x = np.interp(t, np.arange(n), x).astype(np.float32)
    n = len(x)

    # 2. EQ тангетки: HP/LP + резонанс
    x = _hp(x, j(prof.get("hp", 320)))
    x = _lp(x, j(prof.get("lp", 3000)))
    x = _reson(x, j(prof.get("reson_hz", 1500)), j(prof.get("reson_db", 6.0)))

    # 3. pre-gain + tanh-клиппинг
    g = 10 ** (j(prof.get("pregain_db", 2.0)) / 20)
    drive = prof.get("drive", 1.6)
    x = np.tanh(x * g * drive) / np.tanh(drive)

    # 4. дистанция: пресет с огибающей шума и LP
    preset = prof.get("preset", "near")
    if preset == "flyby":                          # встречка пролетает: глухо->чисто->глухо
        ph = np.linspace(0, np.pi, n)              # синусоидальная огибающая
        env = np.sin(ph)                           # 0 на краях, 1 в середине
        noise_db = np.interp(env, [0, 1], [-15, -30])
        lp_f = np.interp(env, [0, 1], [1400, 3200])
        noise = _noise(n, rng)
        out = np.zeros(n, np.float32)
        step = max(1, SR // 50)                    # автоматизация блоками
        for s in range(0, n, step):
            e = slice(s, min(n, s + step))
            out[e] = _lp(x[e], lp_f[s]) * 10 ** (-4 * (1 - env[s]) / 20) \
                + noise[e] * 10 ** (noise_db[s] / 20) * (np.std(x) + 1e-9)
        x = out
    else:                                          # near / far: статичные уровни
        if preset == "far":
            lp_f, noise_db, vdrop = j(2000), j(-15), 10 ** (-4 / 20)
        else:
            lp_f, noise_db, vdrop = j(3200), j(-30), 1.0
        x = _lp(x, lp_f) * vdrop
        x = x + _noise(n, rng) * 10 ** (noise_db / 20) * (np.std(x) + 1e-9)

    # 5c. post-roll: хвост шумодава (керчанк) или роджер-бип (25%)
    tail = _kerchunks[int(rng.integers(0, len(_kerchunks)))]
    tail = _to16(tail, 48000)
    if _roger is not None and rng.random() < 0.25:
        tail = _to16(_roger, 48000) * 0.5
    y = np.concatenate([head, x, tail * j(0.7)])
    peak = np.max(np.abs(y)) + 1e-9
    return (y / peak * 0.89).astype(np.float32)


def pick_profile(seed_key):
    """Случайный архетип (с весом) + сид события. Публично — для песочницы и будущих «состояний»."""
    pp = profiles()
    _event[0] += 1
    seed = int.from_bytes(hashlib.md5(str(seed_key).encode()).digest()[:4]) ^ _event[0]
    rng = np.random.default_rng(seed)
    arch = pp["archetypes"]
    weights = [a.get("w", 1.0) for a in arch]
    prof = dict(arch[rng.choice(len(arch), p=np.array(weights) / sum(weights))])
    prof["_seed"] = seed
    return prof
