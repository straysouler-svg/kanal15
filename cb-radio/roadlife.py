"""Жизнь трассы: слои 1–3 поверх world.py (ступень 0, рация не тронута).

Слой 1 — события дороги: рождаются из того, что реально случилось в world.py
(встречи пар, стоянки в одном городе, сданные/сорванные рейсы, поломки, конец
смены, штрафы по канону). Кубик — только внутри события, не вместо него.
У каждого события: время, место, участники, свидетели, слышал ли игрок.

Слой 2 — внутреннее состояние водителя: очки настроения (база дня — темперамент,
как в bonds._day_mood, сдвиги — от событий), у каждого сдвига есть причина
словами; «забота» — одна вещь на уме, меняется событиями.

Слой 3 — погода пар (ровно/тепло/холодок) из матрицы близости
(phrases/drafts_bonds_drivers_2026-11-11.md, раздел 2). Греют стоянки, парный
ход, помощь; холодит «проехал мимо и не ответил». Запреты: Сорока вне игры,
вражды нет, холодок ≤ 2 суток (у пар ступени 3 — ≤ 1 суток), одна холодная
пара одновременно, пара активной арки (Витёк–Вера, свадьба) не трогается.

Состояние — в roadlife_state.json (новый файл; живые state.json / bonds.json /
quest_state.json / world_state.json НЕ трогаем). cb_radio.py не меняется,
world.py — только читать.
"""
import hashlib
import json
import math
import random
from pathlib import Path

from bonds import TEMPER, TEMPER_DEFAULT, MOODS

ORDER = ["grumpy", "tired", "calm", "cheerful"]      # как Bonds.ORDER: grumpy < tired < calm < cheerful

# Стартовая матрица близости (черновик 2026-11-11, раздел 2):
# строка — кто относится, столбец — к кому; 0 чужие · 1 слышали в эфире ·
# 2 свои · 3 близкие. Сорока заморожена: в погоде не участвует.
MATRIX = {
    "mihalych": {"stas": 3, "yanek": 3, "lastochka": 2, "boroda": 2, "soroka": 2,
                 "student": 2, "professor": 1, "petrovna": 2, "ten": 2, "vitek": 2,
                 "ment": 1, "kardan": 1, "rustam": 2, "bahti": 1},
    "stas": {"mihalych": 2, "yanek": 2, "lastochka": 3, "boroda": 2, "soroka": 2,
             "professor": 0, "petrovna": 2, "ten": 1, "vitek": 1, "kardan": 1,
             "lisa": 1, "rustam": 1, "bahti": 2},
    "yanek": {"mihalych": 3, "stas": 2, "lastochka": 1, "boroda": 2, "soroka": 2},
    "lastochka": {"mihalych": 2, "stas": 2, "yanek": 1, "boroda": 3, "soroka": 1,
                  "student": 1, "professor": 1, "petrovna": 2, "ten": 1, "vitek": 1,
                  "ment": 1, "kardan": 1, "lisa": 1, "rustam": 1, "bahti": 1, "vera": 1},
    "boroda": {"mihalych": 2, "stas": 2, "yanek": 2, "lastochka": 3, "soroka": 2,
               "student": 1, "petrovna": 1, "ten": 1, "ment": 2, "kardan": 1,
               "lisa": 1, "rustam": 1, "bahti": 1, "vera": 2},
    "soroka": {"mihalych": 2, "stas": 2, "yanek": 2, "lastochka": 1, "boroda": 2, "student": 1},
    "student": {"mihalych": 3, "stas": 1, "yanek": 1, "lastochka": 1, "boroda": 1,
                "soroka": 1, "professor": 2, "petrovna": 3, "ten": 3, "vitek": 2,
                "ment": 1, "kardan": 1, "lisa": 1, "rustam": 1, "bahti": 2, "vera": 1},
    "professor": {"mihalych": 1, "lastochka": 2, "student": 2, "ten": 2, "kardan": 1,
                  "lisa": 1, "rustam": 2, "bahti": 1, "sova": 1},
    "petrovna": {"mihalych": 2, "stas": 2, "lastochka": 2, "boroda": 1, "student": 3,
                 "ten": 1, "vitek": 2, "sova": 1, "rustam": 2, "vera": 1},
    "ten": {"mihalych": 2, "stas": 1, "lastochka": 1, "boroda": 1, "student": 3,
            "professor": 2, "petrovna": 1, "sova": 3, "ment": 2},
    "vitek": {"mihalych": 2, "stas": 1, "lastochka": 1, "student": 2, "petrovna": 2,
              "bahti": 1, "vera": 2},
    "sova": {"professor": 1, "petrovna": 1, "ten": 3, "ment": 1, "kardan": 1, "lisa": 1},
    "ment": {"mihalych": 1, "lastochka": 1, "boroda": 2, "student": 1, "ten": 2,
             "sova": 1, "kardan": 2, "lisa": 1, "rustam": 1, "vera": 2},
    "kardan": {"mihalych": 1, "stas": 1, "lastochka": 1, "boroda": 1, "student": 1,
               "professor": 1, "sova": 1, "ment": 2, "lisa": 2, "bahti": 2, "vera": 2},
    "lisa": {"stas": 1, "lastochka": 1, "boroda": 1, "student": 1, "professor": 1,
             "sova": 1, "ment": 1, "kardan": 3, "bahti": 1, "vera": 2},
    "rustam": {"mihalych": 2, "stas": 1, "lastochka": 1, "boroda": 1, "student": 1,
               "professor": 2, "petrovna": 2, "ment": 1, "bahti": 3, "vera": 1},
    "bahti": {"mihalych": 1, "stas": 2, "lastochka": 1, "boroda": 1, "student": 2,
              "professor": 1, "vitek": 1, "kardan": 2, "lisa": 1, "rustam": 3, "vera": 1},
    "vera": {"lastochka": 1, "boroda": 2, "student": 1, "petrovna": 1, "vitek": 2,
             "ment": 2, "kardan": 2, "lisa": 2, "rustam": 1, "bahti": 1},
}

# Пара активной арки (свадьба Витька): погода не трогается.
ARC_PAIRS = {tuple(sorted(("vitek", "vera")))}

WEATHER = ("ровно", "тепло", "холодок")

WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

# Позывные (CHARACTERS.md): в дневнике и сводке — везде позывной, не имя.
CALLSIGNS = {"rustam": "Самарканд", "bahti": "Ковбой", "vera": "Кинолог"}

# Женский род: дневник — блокнот Ласточки, окончания по родам.
FEMALE = {"lastochka", "petrovna", "lisa", "vera", "sova"}
MOOD_FEMALE = {"calm": "спокойна", "tired": "устала", "grumpy": "хмурая"}


def pairs_from_matrix():
    """Симметричные пары (без Сороки): {frozenset-like tuple: уровень max(a→b, b→a)}."""
    out = {}
    for a, row in MATRIX.items():
        if a == "soroka":
            continue
        for b, v in row.items():
            if b == "soroka" or v <= 0:
                continue
            k = tuple(sorted((a, b)))
            out[k] = max(out.get(k, 0), v)
    return out


class Roadlife:
    """Слои 1–3. Журналирует события, считает настроение и погоду пар."""

    # настройки баланса (калиброваны стендом tools/roadlife_run.py)
    PAIR_GAP_MIN = 300.0        # минимум игровых минут между событиями пары
    MEET_RADIUS = 0.8           # доля радиуса рации для «встретились»
    BREAK_P = 6e-4              # поломка на тик (5 игровых минут) на длинном перегоне
    BREAK_MIN_LEG = 12000.0     # м: поломка только на длинном перегоне
    FINE_P = 8e-5               # штраф на тик (канон: чаще у Бороды)
    COLD_P = 0.25               # «проехал мимо» при встрече, если адресат хмур/устал
    COLD_STEP = 4.0             # насколько холодит «проехал мимо» (порог тепла = 3)
    LONGING_DAYS = 5            # столько дней без встречи у ступени 3 — «давно не виделись»
    COLD_CAP_3 = 720.0          # холодок у пар ступени 3 — не дольше суток (ворчание)
    COLD_CAP = 2880.0           # холодок ≤ 2 суток
    COLD_MIN = 180.0            # ниже 3 игровых часов холодок не считается (шум из одного тика)
    HEAT_WARM = 3.0             # порог тепла; −3 — холодок
    STEP_PTS = 20.0             # очков на шаг настроения от базы дня
    MAX_SHIFT = 3               # не больше шагов от базы дня
    REAL_SEC_PER_GAME_MIN = 3.0 # трассовый масштаб времени ×20 (5 игр. мин = 15 наст. с)

    def __init__(self, world, names, seed=7, state_path=None, meet_radius=None,
                 diminishing=False):
        self.w = world
        self.names = names
        self.rng = random.Random(seed)
        self.pairs = pairs_from_matrix()
        self.state_path = Path(state_path) if state_path else None
        if meet_radius:
            self.MEET_RADIUS = meet_radius
        self.diminishing = diminishing            # убывающая отдача: греет первая встреча пары за сутки
        # слой 2
        self.pts = {k: 0.0 for k in names}                 # очки сдвига от базы дня
        self.reasons = {k: [] for k in names}              # [(game_min, причина)]
        self.care = {k: (0.0, "") for k in names}          # (game_min, «что на уме»)
        self.daily_mood = {k: [] for k in names}           # итог суток (доли времени)
        self._day_samples = {k: [] for k in names}         # замеры 4 раза в сутки
        self._last_day = None
        # слой 3
        self.weather = {p: [0.0, 0.0, "ровно"] for p in self.pairs}  # heat, since, state
        self.last_meet = {p: 0.0 for p in self.pairs}
        self.cold_pair = None                              # одна холодная пара
        self.cold_log = []                                 # (pair, начало, конец)
        # слой 1
        self.events = []
        self.debug_log = []                              # отладка: расписание и прочий шум
        self._meet_day = {p: -1 for p in self.pairs}     # убывающая отдача: день последней встречи
        # пересказ: свидетель помнит событие 2 игровых суток и рассказывает игроку в радиусе
        self._knowledge = {k: {} for k in names}         # key -> {id события: срок годности gm}
        self._retold = set()                             # события, до которых дошёл пересказ
        self.retold_events = []                          # сами события-пересказы
        self.player_mode = ""                            # как едет условный игрок (для сводки)
        self._pair_gap = {p: -1e9 for p in self.pairs}
        self._prev_route = {}
        self._job = {}                                     # key -> (game_min, остаток км)
        self._prev_active = {}
        self._broken = {}                                  # key -> игровая минута поломки
        self._rain_days = set()
        self._nr_day = None                              # ночной рейс Студента: день начала

    # ------------------------------------------------------------------ утилиты
    def name(self, key):
        return CALLSIGNS.get(key) or self.names.get(key, key)

    def place(self, x, z):
        t = self.w.roads.nearest(x, z)
        return self.w.cities[t][0]

    NEAR_CITY_M = 20000.0       # ближе 20 км — называем город; дальше — перегон

    def place_near(self, x, z, route=None):
        """Честное место: город, если он рядом, иначе перегон A—B по текущему плечу маршрута."""
        t = self.w.roads.nearest(x, z)
        cx, cz = self.w.roads.xz(t)
        if math.hypot(cx - x, cz - z) <= self.NEAR_CITY_M:
            return self.w.cities[t][0]
        if route and len(route) > 1:
            try:
                return f"перегон {self.w.cities[route[0]][0]}—{self.w.cities[route[1]][0]}"
            except (KeyError, IndexError):
                pass
        return f"трасса у {self.w.cities[t][0]}"

    def between(self, d):
        return self.place_near(d.x, d.z, getattr(d, "route", None))

    def witnesses(self, x, z, exclude=()):
        out = []
        for k, o in self.w.drivers.items():
            if k in exclude or k == "soroka" or o.x is None or o.resting > 0:
                continue
            if k in self.w.inside or math.hypot(o.x - x, o.z - z) < self.w.range:
                out.append(k)
        return out

    def shift(self, key, d, why, gm):
        self.pts[key] = max(-self.MAX_SHIFT * self.STEP_PTS,
                            min(self.MAX_SHIFT * self.STEP_PTS, self.pts[key] + d))
        if why:
            self.reasons[key].append((gm, why))
            self.reasons[key] = self.reasons[key][-500:]  # запас под дневник (пишется в конце месяца)

    def set_care(self, key, gm, text):
        self.care[key] = (gm, text)

    def base_mood(self, key, day):
        """База дня — темперамент, тот же бросок, что и в bonds._day_mood."""
        h = int(hashlib.md5(f"{key}|{int(day)}".encode()).hexdigest(), 16)
        r = (h % 1000) / 1000.0
        ch, ca, ti, gr = TEMPER.get(key, TEMPER_DEFAULT)
        return "cheerful" if r < ch else "calm" if r < ch + ca else "tired" if r < ch + ca + ti else "grumpy"

    def mood_now(self, key, day):
        base = self.base_mood(key, day)
        i = ORDER.index(base) + int(round(self.pts[key] / self.STEP_PTS))
        return ORDER[max(0, min(3, i))]

    # ------------------------------------------------------------------ погода пар
    def _weather_step(self, pair, dheat, gm):
        st = self.weather[pair]
        arc = pair in ARC_PAIRS
        st[0] = st[0] + dheat
        if arc:
            st[0] = max(-2.9, min(2.9, st[0]))            # арка: до холодка не доходит
        self._weather_resolve(gm)

    def _weather_resolve(self, gm):
        """Состояние пар из тепла: тепло/ровно/холодок + запреты (одна холодная пара,
        арки не трогаем). Выход из холодка — сразу в «тепло» (помирились)."""
        for pair, st in self.weather.items():
            new = "тепло" if st[0] >= self.HEAT_WARM else "холодок" if st[0] <= -self.HEAT_WARM else "ровно"
            if new == "холодок" and st[2] != "холодок":
                if pair in ARC_PAIRS or (self.cold_pair not in (None, pair)):
                    st[0] = -2.9                            # одна холодная пара + не арка
                    new = "ровно"
                else:
                    self.cold_pair = pair
            if st[2] == "холодок" and new != "холодок":
                self.cold_pair = None
                if gm - st[1] < self.COLD_MIN:          # слишком короткий — шум, «как будто не было»
                    st[0], st[1], st[2] = 0.0, gm, "ровно"
                    if new == "тепло":
                        continue
                    new = "ровно"
                else:
                    self.cold_log.append((pair, st[1], gm))
                    if new == "ровно":
                        st[0] = 1.5                             # помирились — чуть теплее прежнего
                        new = "тепло"
            if new != st[2]:
                st[1], st[2] = gm, new

    def _weather_tick(self, gm):
        for st in self.weather.values():
            st[0] *= 0.9985                               # погода тает: полураспад ~ 7,7 ч
        for pair, st in self.weather.items():
            if st[2] != "холодок":
                continue
            cap = self.COLD_CAP_3 if self.pairs[pair] >= 3 else self.COLD_CAP
            if gm - st[1] >= cap:                         # примирение по времени (потолок)
                st[0] = 1.5
                st[1], st[2] = gm, "тепло"
                self.cold_pair = None
                self.cold_log.append((pair, gm - cap, gm))
        self._weather_resolve(gm)

    # ------------------------------------------------------------------ события
    def _log(self, gm, place, kind, who, witnesses, audible, note=""):
        self.events.append({"gm": gm, "place": place, "kind": kind, "who": who,
                            "wit": witnesses, "audible": audible, "note": note,
                            "moods": {k: self.mood_now(k, int(gm // 1440)) for k in who}})

    def _pair_events(self, gm, night):
        w = self.w
        r = self.rng
        for pair, lvl in self.pairs.items():
            if gm - self._pair_gap[pair] < self.PAIR_GAP_MIN:
                continue
            a, b = pair
            da, db = w.drivers[a], w.drivers[b]
            if da.x is None or db.x is None:
                continue
            both_rest = da.resting > 0 and db.resting > 0
            if both_rest:
                ca = w.roads.nearest(da.x, da.z)
                if ca != w.roads.nearest(db.x, db.z):
                    continue
                dist = math.hypot(da.x - db.x, da.z - db.z)
                if dist > w.range:
                    continue
                kind = "стоянка вместе"
            else:
                if not (w.active(da, night) and w.active(db, night)):
                    continue
                if da.resting > 0 or db.resting > 0:
                    continue
                dist = math.hypot(da.x - db.x, da.z - db.z)
                if dist > w.range * self.MEET_RADIUS:
                    continue
                hax, haz = w.heading(da)
                hbx, hbz = w.heading(db)
                same = hax * hbx + haz * hbz > 0.5
                kind = "шли парой" if same else "разъехались на трассе"
            x, z = (da.x + db.x) / 2, (da.z + db.z) / 2
            self._pair_gap[pair] = gm
            longing = lvl >= 3 and gm - self.last_meet[pair] > self.LONGING_DAYS * 1440
            # убывающая отдача: повтор в тот же день — ноль; раз в сутки — треть;
            # раз в двое — две трети; разлука трое суток и больше — полная.
            # Долгая разлука греет сильнее частой встречи.
            gap = gm - self.last_meet[pair]
            mult = 1.0
            if self.diminishing:
                if self._meet_day[pair] == int(gm // 1440):
                    mult = 0.0
                else:
                    mult = 1.0 if gap >= 4320 else 0.66 if gap >= 2880 else 0.33
            self._meet_day[pair] = int(gm // 1440)
            self.last_meet[pair] = gm
            wit = self.witnesses(x, z, exclude=pair)
            audible = any(k in w.inside for k in pair) or any(k in w.inside for k in wit)
            ma, mb = self.mood_now(a, gm // 1440), self.mood_now(b, gm // 1440)
            note = ""
            if lvl < 2:
                # «слышали в эфире»: встреча слабая — настроение чуть тянет вверх,
                # в погоду не лезет, в дневник не пишем (иначе шумит)
                self.shift(a, max(mult, 0.2), f"слышал в эфире {self.name(b)}", gm)
                self.shift(b, max(mult, 0.2), f"слышал в эфире {self.name(a)}", gm)
                continue
            if kind == "стоянка вместе":
                self.shift(a, 7 * mult, f"стоянка с {self.name(b)}", gm)
                self.shift(b, 7 * mult, f"стоянка с {self.name(a)}", gm)
                self._weather_step(pair, 3 * mult, gm)
            elif kind == "шли парой":
                self.shift(a, 6 * mult, f"ехал в паре с {self.name(b)}", gm)
                self.shift(b, 6 * mult, f"ехал в паре с {self.name(a)}", gm)
                self._weather_step(pair, 2 * mult, gm)
            else:
                self.shift(a, 3 * mult, f"встретил на трассе {self.name(b)}", gm)
                self.shift(b, 3 * mult, f"встретил на трассе {self.name(a)}", gm)
                self._weather_step(pair, 1 * mult, gm)
            if longing:
                kind = "давно не виделись"
                self.shift(a, 10, f"давно не видел {self.name(b)} — аж обрадовался", gm)
                self.shift(b, 10, f"давно не видел {self.name(a)} — аж обрадовался", gm)
                wst = self.weather[pair]
                if wst[2] == "холодок":
                    self.cold_pair = None
                    self.cold_log.append((pair, wst[1], gm))
                wst[0], wst[1], wst[2] = 4.0, gm, "тепло"
                self.set_care(a, gm, f"давно не виделся с {self.name(b)}")
            # «проехал мимо и не ответил»: адресат хмур/устал, шанс COLD_P
            grump = [k for k, m in ((a, ma), (b, mb)) if m in ("grumpy", "tired")]
            if grump and self.rng.random() < self.COLD_P and lvl <= 2:
                cold, other = grump[0], b if grump[0] == a else a
                before = self.weather[pair][2]
                self._weather_step(pair, -self.COLD_STEP, gm)
                self.shift(cold, -2, f"проехал мимо {self.name(other)} — был не в духе", gm)
                self.shift(other, -5, f"{self.name(cold)} проехал мимо и не ответил", gm)
                self.set_care(other, gm, f"{self.name(cold)} проехал мимо — обиделся")
                if self.weather[pair][2] == "холодок" and before != "холодок":
                    kind = f"проехал мимо ({self.name(cold)} не ответил)"
                    note = "холодок"
                else:
                    kind = f"проехал мимо ({self.name(cold)} не ответил)"
                    note = self.weather[pair][2]
            # заражение настроением: близкий тянет за собой
            if lvl >= 3 and not note:
                cheerful = [k for k, m in ((a, ma), (b, mb)) if m == "cheerful"]
                if cheerful and self.rng.random() < 0.3:
                    other = b if cheerful[0] == a else a
                    if self.mood_now(other, gm // 1440) in ("tired", "grumpy"):
                        self.shift(other, 3 * mult, f"{self.name(cheerful[0])} взбодрил по дороге", gm)
            self._log(gm, self.place_near(x, z, getattr(da, "route", None)), kind, list(pair), wit, audible,
                      note or self.weather[pair][2])

    @staticmethod
    def _active_hours(d):
        s = str(d.schedule or "06-22")
        if s == "any":
            return 24.0
        try:
            a, b = (float(v) for v in s.split("-"))
        except ValueError:
            return 14.0
        return ((b - a) % 24) or 24.0

    def _job_events(self, gm):
        w = self.w
        for k, d in w.drivers.items():
            if k == "soroka":
                continue
            was_rest = self._prev_route.get(k) == "rest"
            if d.x is None:
                continue
            if d.resting > 0:
                if not was_rest and self._job.get(k) and self._prev_active.get(k):
                    # рейс сдан: _advance ставит resting при выгрузке.
                    # Ожидание считаем по активным часам: вне смены водитель не едет,
                    # иначе каждый ночной перерыв превращал бы рейс в «опоздание».
                    start_gm, rem_km = self._job[k]
                    h_act = self._active_hours(d)
                    # минуты за рулём — реальные, переводим в игровые (масштаб времени ×20)
                    expected = rem_km * 1000.0 / max(d.speed, 5.0) / self.REAL_SEC_PER_GAME_MIN
                    expected *= 24.0 / h_act * 1.15                # в пересчёте на сутки + резерв
                    actual = gm - start_gm
                    if actual > expected * 1.5 + 45:
                        self.shift(k, -10, "опоздал с рейсом", gm)
                        self.set_care(k, gm, "опаздывает с рейсом")
                        self._log(gm, self.place_near(d.x, d.z, getattr(d, "route", None)),
                                  "опоздал с рейсом", [k],
                                  self.witnesses(d.x, d.z, (k,)),
                                  k in w.inside)
                    else:
                        self.shift(k, 1, "рейс сдал вовремя", gm)
                        if self.rng.random() < 0.2:      # в дневнике — каждый пятый, иначе шум
                            self._log(gm, self.place_near(d.x, d.z, getattr(d, "route", None)),
                                      "рейс сдан", [k],
                                      self.witnesses(d.x, d.z, (k,)), k in w.inside)
                self._prev_route[k] = "rest"
                continue
            if was_rest and len(d.route) > 1:
                # выезд на новый рейс — считаем остаток для прикидки «вовремя ли»
                try:
                    pts = [(d.x, d.z)] + [w.roads.xz(t) for t in d.route[1:]]
                    rem = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                              for a, b in zip(pts, pts[1:])) / 1000.0
                except Exception:
                    rem = 50.0
                self._job[k] = (gm, rem)
            self._prev_route[k] = "drive"

    def _solo_events(self, gm, night, rain):
        w = self.w
        r = self.rng
        for k, d in w.drivers.items():
            if d.x is None or k == "soroka":              # Сорока вне игры: ни пар, ни событий
                continue
            active = w.active(d, night)
            was = self._prev_active.get(k)
            if was and not active and not rain:
                self.shift(k, -1, "смена кончилась, вымотался", gm)
                # расписание, не жизнь: в дневник и счёт событий не пишем, только отладка
                self.debug_log.append((gm, self.place_near(d.x, d.z, getattr(d, "route", None)),
                                       "конец смены", k))
            self._prev_active[k] = active
            if not active or d.resting > 0:
                self._broken.pop(k, None)
                continue
            # поломка — редкий бросок на длинном перегоне
            if k not in self._broken and len(d.route) > 1:
                tx, tz = w.roads.xz(d.route[1])
                if math.hypot(tx - d.x, tz - d.z) > self.BREAK_MIN_LEG \
                        and r.random() < self.BREAK_P:
                    self._broken[k] = gm
                    self.shift(k, -12, "сломался посреди перегона", gm)
                    self.set_care(k, gm, "грузовик встал — ждёт помощи")
                    wit = self.witnesses(d.x, d.z, (k,))
                    self._log(gm, self.between(d), "поломка", [k], wit, k in w.inside)
                    # крюк на помощь: близкий в пределах 120 км приезжает через 1–3 тика
                    helper = None
                    for pair, lvl in self.pairs.items():
                        if lvl < 2 or k not in pair:
                            continue
                        o = pair[0] if pair[1] == k else pair[1]
                        od = w.drivers[o]
                        if od.x is None or od.resting > 0 or not w.active(od, night):
                            continue
                        if math.hypot(od.x - d.x, od.z - d.z) < 120000:
                            helper = o
                            break
                    if helper:
                        self._pending_help = (gm + r.uniform(5, 15), k, helper)
            # штраф — у того, кому по канону (Борода), редко и у других
            p = self.FINE_P * (8.0 if k == "boroda" else 1.0)
            if r.random() < p:
                self.shift(k, -8, "штраф прилетел", gm)
                self.set_care(k, gm, "опять штраф — деньги жгут")
                self._log(gm, self.between(d), "штраф", [k],
                          self.witnesses(d.x, d.z, (k,)), k in w.inside)
            if rain and active:
                self.shift(k, -0.02, "", gm)              # дождь понемногу давит
        # помощь приходит
        ph = getattr(self, "_pending_help", None)
        if ph and gm >= ph[0]:
            _, victim, helper = ph
            self._pending_help = None
            self._broken.pop(victim, None)
            hv, hh = w.drivers[victim], w.drivers[helper]
            if hv.x is not None and hh.x is not None:
                self.shift(helper, +12, f"свернул с маршрута — помог {self.name(victim)}", gm)
                self.shift(victim, +6, f"{self.name(helper)} приехал на помощь", gm)
                self.set_care(victim, gm, "")
                self.set_care(helper, gm, f"помог {self.name(victim)} — сам теперь опаздывает")
                pair = tuple(sorted((victim, helper)))
                if pair in self.weather:
                    self._weather_step(pair, +4, gm)
                x, z = (hv.x + hh.x) / 2, (hv.z + hh.z) / 2
                wit = self.witnesses(x, z, (victim, helper))
                aud = victim in w.inside or helper in w.inside or any(t in w.inside for t in wit)
                self._log(gm, self.place_near(x, z, getattr(hv, "route", None)), "крюк на помощь",
                          [victim, helper],
                          wit, aud, self.weather.get(pair, [0, 0, "ровно"])[2])

    # ------------------------------------------------------------------ шаг
    def step(self, gm, night, rain):
        """Один тик модели после world.update. gm — игровые минуты."""
        day = int(gm // 1440)
        n_events = len(self.events)
        self._weather_tick(gm)
        self._pair_events(gm, night)
        self._job_events(gm)
        self._solo_events(gm, night, rain)
        # пересказ: свидетели новых событий запоминают их на 2 игровых суток
        for e in self.events[n_events:]:
            expiry = e["gm"] + 2 * 1440.0
            for k in e["wit"]:
                if k in self._knowledge:
                    self._knowledge[k][id(e)] = expiry
        # кто в радиусе игрока — тот рассказывает: событие доезжает до игрока однажды
        if self.w.inside:
            for k in self.w.inside:
                know = self._knowledge.get(k)
                if not know:
                    continue
                for eid, expiry in list(know.items()):
                    if expiry < gm:
                        del know[eid]
                        continue
                    if eid in self._retold:
                        continue
                    e = next((x for x in self.events if id(x) == eid), None)
                    if e is None or e["audible"]:
                        self._retold.add(eid)
                        continue
                    self._retold.add(eid)
                    self.retold_events.append(e)
        if int(gm) % 240 < 5:                              # замер настроения 4 раза в сутки
            for k in self.names:
                self._day_samples[k].append(self.mood_now(k, day))
        if day != self._last_day:
            if self._last_day is not None:
                for k in self.names:
                    self.daily_mood[k].extend(self._day_samples[k])
                    self._day_samples[k] = []
            self._last_day = day
            for k in self.names:                            # новый день — сдвиги тают к темпераменту
                self.pts[k] *= 0.15

    def _mood_word(self, key, mood):
        if key in FEMALE and mood in MOOD_FEMALE:
            return MOOD_FEMALE[mood]
        return MOODS[mood]["name"]

    # ------------------------------------------------------------------ ночной рейс Студента (стенд)
    def student_night(self, gm, night):
        """Ночной рейс — исключение из расписания (решение 11.11, только стенд):
        ночью Студент устаёт раньше смены и ему страшно — повод для заботы Тени."""
        d = self.w.drivers.get("student")
        if d is None or d.x is None or d.resting > 0 or not night \
                or not self.w.active(d, night):
            return
        day = int(gm // 1440)
        if self._nr_day != day:                    # начало ночного рейса — одна запись
            self._nr_day = day
            self.shift("student", -0.4, "ночной рейс — темно и одиноко", gm)   # усталость копится всю ночь
            self.set_care("student", gm, "ночью одному страшно")
            self._log(gm, self.place(d.x, d.z), "ночной рейс (исключение из расписания)",
                      ["student"], self.witnesses(d.x, d.z, ("student",)),
                      "student" in self.w.inside)
            td = self.w.drivers.get("ten")
            if td is not None:
                self.shift("ten", 0, "Студент ночью один на трассе — держу ухо востро", gm)
                self.set_care("ten", gm, "Студент где-то один ночью — присмотреть бы")
        else:
            self.shift("student", -0.4, "ночной рейс — темно и одиноко", gm)   # усталость копится всю ночь
            self.set_care("student", gm, "ночью одному страшно")

    # ------------------------------------------------------------------ вывод
    def fmt_gm(self, gm):
        d = int(gm // 1440)
        mins = int(gm % 1440)
        return f"{WEEKDAYS[d % 7]} {mins // 60:02d}:{mins % 60:02d}"

    def diary(self, days=None):
        lines = []
        start = self.events[0]["gm"] if self.events else 0
        limit = start + (days or 10**9) * 1440
        for e in self.events:
            if e["gm"] > limit:
                break
            who = " и ".join(self.name(k) for k in e["who"])
            moods = ", ".join(f"{self.name(k)} — {self._mood_word(k, e['moods'][k])}"
                              for k in e["who"])
            wit = ""
            if e["wit"]:
                wit = " Слышали: " + ", ".join(self.name(k) for k in e["wit"][:4]) + "."
            aud = " [в эфире]" if e["audible"] else ""
            note = f" Погода пары: {e['note']}." if e["note"] in WEATHER else ""
            reason = ""
            k0 = e["who"][0]
            rs = [t for t in self.reasons[k0] if t[0] <= e["gm"]]
            if rs:
                reason = f" На уме: {rs[-1][1]}."
            lines.append(f"{self.fmt_gm(e['gm'])}, {e['place']}. {who} — {e['kind']}. "
                         f"{moods}.{note}{wit}{reason}{aud}")
        return "\n".join(lines) + ("\n" if lines else "")

    def summary(self, days, real_sec_per_game_min=3.0):
        out = []
        real_min_total = days * 1440.0 * real_sec_per_game_min / 60.0   # игровые сутки = 72 мин игры
        npairs = len(self.pairs)
        met = {p: 0 for p in self.pairs}
        for e in self.events:
            if len(e["who"]) == 2:
                p = tuple(sorted(e["who"]))
                if p in met:
                    met[p] += 1
        never = [p for p, n in met.items() if n == 0 and self.pairs[p] >= 2]
        out.append(f"Пар (уровень >=2): {sum(1 for p in self.pairs if self.pairs[p] >= 2)} "
                   f"из {npairs} всего связей")
        met2 = {p: n for p, n in met.items() if self.pairs[p] >= 2}
        out.append(f"Встреч на пару за {days} дн. (медиана): "
                   f"{sorted(met2.values())[len(met2) // 2] if met2 else 0}")
        out.append(f"Пар >=2, ни разу не встретившихся: {len(never)}")
        for p in sorted(never, key=lambda p: -self.pairs[p]):
            out.append(f"   нет встреч: {self.name(p[0])} ↔ {self.name(p[1])} (ур. {self.pairs[p]})")
        out.append("")
        out.append("Доли настроений за месяц против базы дня и TEMPER (в духе/спокоен/устал/хмурый):")
        report_order = ["cheerful", "calm", "tired", "grumpy"]
        max_dev = max_dev_base = max_base_noise = 0.0
        state_means = [0.0, 0.0, 0.0, 0.0]
        n_actors = 0
        for k in self.names:
            if k == "soroka":
                continue                                  # вне игры — не участвует в отчёте
            hist = self.daily_mood[k]
            if not hist:
                continue
            shares = [hist.count(m) / len(hist) for m in report_order]
            tp = TEMPER.get(k, TEMPER_DEFAULT)
            # база месяца: детерминированный дневной бросок темперамента (30 дней — мало,
            # сама база гуляет от TEMPER до ±15 п.п.; поэтому две проверки)
            base_hist = [self.base_mood(k, day) for day in range(days) for _ in range(6)]
            bshares = [base_hist.count(m) / len(base_hist) for m in report_order]
            dev = max(abs(s - t) for s, t in zip(shares, tp))
            dev_b = max(abs(s - b) for s, b in zip(shares, bshares))
            max_base_noise = max(max_base_noise,
                                 max(abs(b - t) for b, t in zip(bshares, tp)))
            max_dev = max(max_dev, dev)
            max_dev_base = max(max_dev_base, dev_b)
            n_actors += 1
            for i, (s, t) in enumerate(zip(shares, tp)):
                state_means[i] += s - t
            out.append(f"   {self.name(k):12s} факт " +
                       " ".join(f"{s * 100:4.0f}%" for s in shares) +
                       " | база " + " ".join(f"{b * 100:4.0f}%" for b in bshares) +
                       " | темпер " + " ".join(f"{t * 100:4.0f}%" for t in tp) +
                       f" | Δтемпер {dev * 100:3.0f} п.п., Δбаза {dev_b * 100:3.0f} п.п.")
        if n_actors:
            state_means = [m / n_actors for m in state_means]
        sys_shift = max(abs(m) for m in state_means)
        ok = max_dev_base <= 0.10 and max_dev <= max(max_base_noise + 0.10, 0.15) and sys_shift <= 0.05
        out.append(f"   ПРОВЕРКА: события vs база месяца {max_dev_base * 100:.0f} п.п. (лимит 10) — "
                   f"влияние событий; факт vs TEMPER {max_dev * 100:.0f} п.п. при собственном шуме базы "
                   f"{max_base_noise * 100:.0f} п.п. + 10 (30 дневных бросков — TEMPER на месяце шумит сам); "
                   f"системный сдвиг {sys_shift * 100:.0f} п.п. (лимит 5) — "
                   f"{'держится' if ok else 'НЕ держится'}")
        out.append(f"   Средний сдвиг по состояниям: " +
                   " ".join(f"{m * 100:+.0f}" for m in state_means))
        out.append("")
        out.append(f"Холодков за месяц: {len(self.cold_log)}")
        longest = max((e - s for _, s, e in self.cold_log), default=0)
        out.append(f"Самый долгий холодок: {longest / 60:.1f} ч "
                   f"(лимит {self.COLD_CAP / 60:.0f} ч; у пар ур.3 — {self.COLD_CAP_3 / 60:.0f} ч)")
        for p, s, e in self.cold_log:
            out.append(f"   {self.name(p[0])} ↔ {self.name(p[1])}: "
                       f"{self.fmt_gm(s)} → {self.fmt_gm(e)} ({(e - s) / 60:.1f} ч)")
        aud = [e for e in self.events if e["audible"]]
        start_day = int((self.events[0]["gm"] if self.events else 0) // 1440)
        aud_day = {d: 0 for d in range(start_day, start_day + days)}   # все дни, включая нулевые
        for e in aud:
            aud_day[int(e["gm"] // 1440)] = aud_day.get(int(e["gm"] // 1440), 0) + 1
        silent_days = sum(1 for v in aud_day.values() if v == 0)
        per_hour = len(aud) / (real_min_total / 60.0)
        trip_avg = per_hour * 1.5                       # 90 минут игры
        day_real_min = 1440.0 * real_sec_per_game_min / 60.0
        trip_worst = min(aud_day.values()) * 90.0 / day_real_min
        ret_day = {d: 0 for d in range(start_day, start_day + days)}
        for e in self.retold_events:
            ret_day[int(e["gm"] // 1440)] = ret_day.get(int(e["gm"] // 1440), 0) + 1
        ret_per_hour = len(self.retold_events) / (real_min_total / 60.0)
        ret_trip = ret_per_hour * 1.5
        ret_trip_worst = min(ret_day.values()) * 90.0 / day_real_min
        out.append("")
        out.append(f"Как едет игрок: {self.player_mode or 'кольцо по 14 крупным городам, 22 м/с, ночью стоянка'}")
        out.append("Масштаб времени: ×20 на трассе (1 игровая минута = "
                   f"{real_sec_per_game_min:.0f} с; канал scale float @700 в design_telemetry_2026-11-11.md; "
                   "число «5 игр. мин = 15 наст. с» — из брифа проверки, в документе не подтверждено)")
        out.append("")
        out.append("Главная метрика — на настоящие часы игры:")
        out.append(f"   Вживую в эфире: {len(aud)} за {real_min_total / 60:.1f} ч игры "
                   f"= {per_hour:.2f} в час (всего событий журнала {len(self.events)}; "
                   f"концов смены в отладке: {len(self.debug_log)})")
        out.append(f"   Поездка 90 мин вживую: в среднем {trip_avg:.1f}, худший день {trip_worst:.1f}; "
                   f"дней без единого события в эфире: {silent_days} из {days}")
        out.append(f"   Пересказ (свидетель в радиусе помнит событие 2 игр. суток): "
                   f"{len(self.retold_events)} за месяц = {ret_per_hour:.2f} в час")
        out.append(f"   Поездка 90 мин с пересказом: в среднем {ret_trip:.1f}, "
                   f"худший день {ret_trip_worst:.1f}")
        all_days = sorted(set(aud_day) | set(ret_day))
        comb_day = {d: aud_day.get(d, 0) + ret_day.get(d, 0) for d in all_days}
        comb_per_hour = (len(aud) + len(self.retold_events)) / (real_min_total / 60.0)
        out.append(f"   Поездка 90 мин вживую+пересказ: в среднем {comb_per_hour * 1.5:.1f}, "
                   f"худший день {min(comb_day.values()) * 90.0 / day_real_min:.1f}")
        ts = met.get(tuple(sorted(("student", "ten"))), 0)
        out.append(f"   Встреч Тень ↔ Студент за месяц: {ts}")
        soroka_in = [e for e in self.events
                     if "soroka" in e["who"] or "soroka" in e["wit"]]
        out.append(f"Сорока в событиях/свидетелях: {len(soroka_in)} (должно быть 0)")
        cold_states = [e["note"] for e in self.events if e["note"] == "холодок"]
        out.append(f"Пометок «холодок» у событий: {len(cold_states)} — погода пары на момент события; "
                   "в «холодков за месяц» идут только полноценные (≥3 ч), поэтому числа разные")
        return "\n".join(out) + "\n"

    def save_state(self):
        if not self.state_path:
            return
        st = {"weather": {f"{a}|{b}": v for (a, b), v in self.weather.items()},
              "care": self.care, "last_meet": {f"{a}|{b}": v for (a, b), v in self.last_meet.items()}}
        try:
            self.state_path.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass
