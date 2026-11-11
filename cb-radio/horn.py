# -*- coding: utf-8 -*-
"""Синтез гудка грузовика «с дороги» для «Канала 15».

Чистый модуль: только numpy/scipy, никаких импортов рации.
Звук собственный (аддитивный синтез) — для распространения в Steam.

API:
    horn_buffer(timbre, distance_m, rel_speed_ms=0, side='left'|'center',
                sr=48000, duration=2.5, pattern=None) -> np.ndarray (n, 2) float32
    pattern = None — один сплошной гудок на всю длительность;
    [(start_s, dur_s), ...] — ритм от характера (два коротких, частит «та-та-та»...).
"""

import numpy as np

C_AIR = 340.0          # скорость звука, м/с
SR_DEFAULT = 48000
AUDIBILITY_FLOOR = 0.03   # ниже этой амплитуды — тишина (порог слышимости)
REF_DIST = 60.0           # масштаб затухания

# Ритмы гудка по рисункам Летописца (phrases/drafts_horn_2026-11-11.md, раздел «Рисунок гудка»):
# ключ -> (тембр-класс, pattern). Пилот 11.11: soroka/витёк — high, тень — bass.
HORN_RHYTHMS = {
    "mihalych": ("old_low", [(0.0, 0.9), (1.25, 1.0)]),
    "stas": ("old_low", [(0.0, 0.16), (0.28, 0.16), (0.56, 0.16), (0.84, 0.16)]),
    "yanek": ("old_low", [(0.0, 1.9)]),
    "lastochka": ("high", [(0.0, 0.35), (0.6, 0.35)]),
    "boroda": ("bass", [(0.0, 2.3)]),
    "soroka": ("high", [(0.0, 0.4), (0.65, 0.4)]),
    "student": ("old_low", [(0.0, 0.5), (1.0, 0.8)]),
    "professor": ("old_low", [(0.0, 0.4), (0.8, 0.4)]),
    "petrovna": ("old_low", [(0.0, 0.3), (0.55, 0.3), (1.1, 0.3)]),
    "ten": ("bass", [(0.0, 0.7)]),
    "vitek": ("high", [(0.0, 0.14), (0.24, 0.14), (0.48, 0.14), (0.72, 0.14), (0.96, 0.14)]),
    "sova": ("old_low", [(0.0, 0.55)]),
    "ment": ("old_low", [(0.0, 0.4), (1.4, 0.4), (2.8, 0.4)]),
    "kardan": ("bass", [(0.0, 1.6)]),
    "lisa": ("old_low", [(0.0, 0.3), (0.55, 0.38)]),
    "rustam": ("old_low", [(0.0, 0.8), (1.2, 0.8)]),
    "bahti": ("bass", [(0.0, 0.22), (0.42, 0.3)]),
    "vera": ("bass", [(0.0, 0.3)]),
    "default": ("old_low", None),
}

# Тембры: (freq, amp) — основа, второй тон, обертона.
# Тембр от машины, ритм (длительность/повторы) задаётся снаружи.
TIMBRES = {
    # старый низкий двухтонный
    "old_low": {
        "components": [(175.0, 1.0), (220.0, 0.7), (350.0, 0.25), (440.0, 0.15)],
        "am_rate": 5.0, "am_depth": 0.18,
    },
    # мощный басовый
    "bass": {
        "components": [(128.0, 1.0), (162.0, 0.6), (256.0, 0.35), (324.0, 0.2)],
        "am_rate": 4.0, "am_depth": 0.12,
    },
    # высокий у малой машины
    "high": {
        "components": [(330.0, 1.0), (415.0, 0.65), (660.0, 0.3), (830.0, 0.15)],
        "am_rate": 6.0, "am_depth": 0.22,
    },
}


def _distance_profile(distance_m, rel_speed_ms, n, sr):
    """Расстояние до источника по сэмплам: сближение до нуля, затем удаление."""
    t = np.arange(n) / sr
    if rel_speed_ms <= 0:
        return np.full(n, float(distance_m)), np.zeros(n)
    t_ca = distance_m / rel_speed_ms          # момент наибольшего сближения
    v = np.where(t < t_ca, -rel_speed_ms, rel_speed_ms)
    d = np.where(t < t_ca,
                 distance_m - rel_speed_ms * t,
                 rel_speed_ms * (t - t_ca))
    return np.maximum(d, 1.0), v


def horn_buffer(timbre, distance_m, rel_speed_ms=0.0, side="left",
                sr=SR_DEFAULT, duration=2.5, pattern=None):
    """Вернуть стерео-буфер гудка. rel_speed_ms>0 включает проезд с Доплером.
    pattern = [(start_s, dur_s), ...] — ритм; None — сплошной гудок на всю длительность."""
    if timbre not in TIMBRES:
        raise ValueError(f"unknown timbre {timbre!r}: {sorted(TIMBRES)}")
    if pattern:
        duration = max(duration, max(s + d for s, d in pattern) + 0.4)
    n = int(round(duration * sr))
    t = np.arange(n) / sr
    spec = TIMBRES[timbre]

    dist, v = _distance_profile(distance_m, rel_speed_ms, n, sr)

    # Доплер: множитель частоты c/(c + dr/dt) — выше при сближении, ниже при удалении.
    dop = C_AIR / (C_AIR + v)

    # Геометрическое затухание + нижний порог слышимости.
    amp = REF_DIST / (REF_DIST + dist)
    if float(amp.max()) < AUDIBILITY_FLOOR:
        return np.zeros((n, 2), dtype=np.float32)

    # Огибающая: быстрая атака, спад в конце, лёгкая АМ-шероховатость.
    att, rel = 0.04, 0.15
    if pattern:
        env = np.zeros(n)
        for s0, d0 in pattern:
            i0, i1 = int(s0 * sr), min(n, int((s0 + d0) * sr))
            seg = np.minimum((t[i0:i1] - s0) / att, 1.0)
            seg *= np.minimum(np.maximum((s0 + d0 - t[i0:i1]) / rel, 0.0), 1.0)
            env[i0:i1] = np.maximum(env[i0:i1], seg)
    else:
        env = np.minimum(t / att, 1.0)
        env *= np.minimum(np.maximum((duration - t) / rel, 0.0), 1.0)
    am = 1.0 + spec["am_depth"] * np.sin(2 * np.pi * spec["am_rate"] * t)
    amp = amp * env * am

    # Аддитивный синтез с накоплением фазы (мгновенная частота * доплер).
    mono = np.zeros(n)
    for f, a in spec["components"]:
        phase = 2 * np.pi * np.cumsum(f * dop) / sr
        mono += a * np.sin(phase)
    mono /= max(len(spec["components"]) - 1.2, 1.0)
    mono *= amp

    # Поглощение высоких с расстоянием: частота среза убывает с дистанцией.
    # fc(d) = 5500 * exp(-d/450), минимум 140 Гц; плюс «через кабину» ~3800 Гц.
    fc_dist = np.clip(5500.0 * np.exp(-dist / 450.0), 140.0, sr * 0.45)
    a_dist = 1.0 - np.exp(-2 * np.pi * fc_dist / sr)
    y = np.empty(n)
    acc = 0.0
    ad = a_dist
    for i in range(n):
        acc += ad[i] * (mono[i] - acc)
        y[i] = acc
    a_cab = 1.0 - np.exp(-2 * np.pi * 3800.0 / sr)
    acc = 0.0
    for i in range(n):
        acc += a_cab * (y[i] - acc)
        y[i] = acc

    # Стерео: встречный — слева (РФ/Европа), дальний/задний — по центру.
    if side == "left":
        gl, gr = 0.92, 0.38          # лёгкий "размытый" пан, не жёсткий 1/0
    elif side == "right":
        gl, gr = 0.38, 0.92
    else:
        gl, gr = 0.8, 0.8            # центр чуть приглушён — «кабина между»
    stereo = np.column_stack([y * gl, y * gr]).astype(np.float32)

    peak = np.abs(stereo).max()
    if peak > 0.98:
        stereo *= (0.98 / peak)
    return stereo
