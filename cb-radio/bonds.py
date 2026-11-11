"""Дружба и настроение водителей (2026-11-06, идея пользователя: скрытые очки дружбы с каждым водителем).

Дружба — у каждого водителя свои очки 0..255, хранятся между поездками (bonds.json рядом с рацией).
  Новый водитель начинает с 25; кто уже встречался на трассе — чуть больше.
  + разговор с ним (+1, по имени +2, «спасибо»/похвала +3), первый разговор за игровой день +3, встреча на трассе +1;
    за день с одного водителя не больше +15.  − грубость −25.
  Повтор той же темы с тем же водителем за игровые сутки — 0 очков (за «встреча на трассе» — тоже).
  Уровни: 0 незнакомый (<35) · 1 знакомый (35+) · 2 приятель (60+) · 3 друг (150+).
  Незнакомый не зовёт тебя по имени (реплики с обращением — только знакомым и дальше).
  Личные реплики (поле "lv", сейчас family/salary/health = 2) звучат только с этого уровня:
    у кого дружбы меньше — эфир уходит в уклончивые фразы (reactions/bond/evade, lv0–1) или общие «не знаю».
  Уровневые пакеты: "lv" = минимум, "lvm" = максимум (lv0-строки — только незнакомцам, lv3 — только друзьям).
  Каждые игровые сутки без разговора с водителем: −1 очко (не ниже 0).

Настроение — у каждого своё на игровой день (бодрое / спокойное / усталое / хмурое), ночью чаще устают,
в дождь чаще хмурятся. Из записанных реплик водитель чаще выбирает те, что по настроению (по тегам эмоций
ElevenLabs в тексте: [tired], [laughs], [frustrated] …). Хмурый дольше дуется на грубость, весёлый отходит быстрее."""
import hashlib
import json
import re
from pathlib import Path

LEVELS = [(0, "незнакомый"), (35, "знакомый"), (60, "приятель"), (150, "друг")]
HEARTS = ["", "♥", "♥♥", "♥♥♥"]
START = 25
DAY_CAP = 15

MOODS = {
    "cheerful": {"name": "в духе", "emoji": "😄",
                 "tags": {"cheerful", "laughs", "laughing", "laugh", "excited", "happy", "giggles", "chuckles",
                          "playful", "amused", "joking", "grins", "overjoyed", "proud", "enthusiastic", "merry"}},
    "calm": {"name": "спокоен", "emoji": "🙂",
             "tags": {"calm", "warmly", "softly", "thoughtful", "relaxed", "pleased", "gentle", "friendly",
                      "smiling", "content", "kind"}},
    "tired": {"name": "устал", "emoji": "😴",
              "tags": {"tired", "sighs", "sigh", "yawns", "yawning", "sleepy", "weary", "exhausted", "resigned",
                       "sad", "melancholic", "quiet", "slowly"}},
    "grumpy": {"name": "хмурый", "emoji": "😠",
               "tags": {"grumpy", "annoyed", "frustrated", "irritated", "outraged", "angry", "stern", "exasperated",
                        "grumbling", "grumbles", "sarcastic", "indignant", "disgruntled", "mutters"}},
}
OPPOSITE = {"cheerful": {"tired", "grumpy"}, "grumpy": {"cheerful"}, "tired": {"cheerful"}, "calm": set()}
_TAG = re.compile(r"\[([^\]]+)\]")
# 2026-11-10 mood2: русские ремарки gpt-audio / XTTS «(смеётся)», «(вздыхает)» — по началу слова.
# Раньше читались только английские теги, и у десяти водителей 77–93 % реплик были «без настроения».
_REMARK = re.compile(r"\(([а-яё][а-яё ,\-]{2,30})\)", re.I)
RU_STEMS = {
    "cheerful": ("смеётся", "смеется", "смеясь", "усмеха", "хихик", "радост", "весел", "восторж", "гордо", "хохо"),
    "calm": ("тихо", "тепло", "мягк", "заботлив", "спокойн", "ласков", "задумч", "нежно"),
    "tired": ("вздыха", "устал", "зева", "сонн", "грустн", "печальн"),
    "grumpy": ("сухо", "ворч", "сердит", "раздраж", "строго", "хмур", "возмущ", "недоволь", "бурч"),
}
RU_SKIP = ("нервн",)          # «нервно смеётся» — не веселье

# Темперамент: доли дневного настроения (в духе, спокоен, устал, хмурый). Раньше у всех было 30/35/20/15.
# Можно переопределить в phrases-файле: actors.<key>.temper = [0.3, 0.35, 0.2, 0.15].
TEMPER_DEFAULT = (0.30, 0.35, 0.20, 0.15)
TEMPER = {
    "mihalych": (0.20, 0.45, 0.15, 0.20), "stas": (0.50, 0.20, 0.20, 0.10), "yanek": (0.10, 0.70, 0.12, 0.08),
    "lastochka": (0.35, 0.30, 0.15, 0.20), "boroda": (0.45, 0.10, 0.10, 0.35), "soroka": (0.50, 0.40, 0.10, 0.00),
    "student": (0.40, 0.25, 0.30, 0.05), "professor": (0.25, 0.50, 0.15, 0.10), "petrovna": (0.35, 0.45, 0.15, 0.05),
    "ten": (0.05, 0.50, 0.35, 0.10), "vitek": (0.40, 0.15, 0.20, 0.25), "sova": (0.15, 0.60, 0.20, 0.05),
    "ment": (0.20, 0.40, 0.20, 0.20), "kardan": (0.50, 0.20, 0.15, 0.15), "lisa": (0.35, 0.40, 0.10, 0.15),
    "rustam": (0.35, 0.50, 0.10, 0.05), "bahti": (0.50, 0.25, 0.15, 0.10), "vera": (0.10, 0.55, 0.15, 0.20),
}


def level_of(points):
    lv = 0
    for i, (lo, _) in enumerate(LEVELS):
        if points >= lo:
            lv = i
    return lv


def tags_of(text):
    out = set()
    for t in _TAG.findall(text or ""):
        out.update(w for w in re.split(r"[\s,]+", t.lower()) if w)
    return out


def remarks_of(text):
    """Russian stage remarks in round brackets: «(смеётся)», «(тихо, тепло)» -> ["смеётся", "тихо", "тепло"]."""
    out = []
    for t in _REMARK.findall(text or ""):
        t = t.lower()
        if any(s in t for s in RU_SKIP):
            continue
        out.extend(w for w in re.split(r"[\s,]+", t) if w)
    return out


def line_mood(text):
    """Which mood a recorded line sounds like (by its emotion tags and Russian remarks), or None.
    A tie between two moods is no mood at all (it used to fall to the first one, «в духе»)."""
    tg = tags_of(text)
    ru = remarks_of(text)
    score = {}
    for m, d in MOODS.items():
        k = len(tg & d["tags"]) + sum(1 for w in ru if w.startswith(RU_STEMS[m]))
        if k:
            score[m] = k
    if not score:
        return None
    top = max(score.values())
    best = [m for m, k in score.items() if k == top]
    return best[0] if len(best) == 1 else None


class Bonds:
    def __init__(self, path, phrases_json=None, log=print):
        self.path = Path(path)
        self.log = log
        self.st = {}
        try:
            self.st = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.st = {}
        self.text = {}          # rel ("reactions/player/greet/05", "<actor>/03", "scenes/x/02") -> text with tags
        self.name_lines = set()  # rels that call the player by name (have a v_neutral version)
        self.lv = {}             # rel -> минимальный уровень дружбы ("lv" в phrases-файле, личные реплики)
        self.line_moods = {}     # rel -> настроение реплики, заданное явно полем "mood" (сильнее тегов)
        self.sched = {}          # actor -> (начало, конец смены в игровых часах) из actors.<key>.schedule
        self.temper = dict(TEMPER)
        self.hour = None         # игровой час (set_world)
        if phrases_json:
            self._load_texts(phrases_json)
        self.day = None          # game day number (from world)
        self.night = False
        self.rain = False
        self.shift = {}          # actor -> (mood steps up/down from the day's mood, monotonic time of the last change)

    # ------------------------------------------------------------ texts
    def _load_texts(self, phrases_json):
        try:
            d = json.loads(Path(phrases_json).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return

        def txt(ln):
            return ln if isinstance(ln, str) else ln.get("text", "")

        def mark(rel, ln):
            if not isinstance(ln, dict):
                return
            if ln.get("mood") in MOODS:
                self.line_moods[rel] = ln["mood"]
            lo = hi = None
            try:
                if "lv" in ln:
                    lo = max(0, min(3, int(ln["lv"])))
            except (TypeError, ValueError):
                lo = None                      # битое "lv" не роняет загрузку
            try:
                if "lvm" in ln:
                    hi = max(0, min(3, int(ln["lvm"])))
            except (TypeError, ValueError):
                hi = None
            if lo is not None or hi is not None:
                self.lv[rel] = (lo, hi)        # (минимальный уровень, максимальный или None)
        for k, a in d.get("actors", {}).items():
            try:
                s0, s1 = (float(v) for v in str(a.get("schedule", "")).split("-"))
                self.sched[k] = (s0 % 24, s1 % 24)
            except (TypeError, ValueError):
                pass                           # "any" / нет расписания: остаётся старое правило «ночью устают»
            try:
                t = [max(0.0, float(v)) for v in a["temper"]]
                if len(t) == 4 and sum(t) > 0:
                    self.temper[k] = tuple(v / sum(t) for v in t)
            except (KeyError, TypeError, ValueError):
                pass
            for i, ph in enumerate(a.get("phrases", []), 1):
                rel = f"{k}/{i:02d}"
                self.text[rel] = txt(ph)
                mark(rel, ph)
                if isinstance(ph, dict) and "v_neutral" in ph:
                    self.name_lines.add(rel)
        for sid, ls in d.get("scenes", {}).items():
            for i, ln in enumerate(ls, 1):
                rel = f"scenes/{sid}/{i:02d}"
                self.text[rel] = txt(ln)
                mark(rel, ln)
                if isinstance(ln, dict) and "v_neutral" in ln:
                    self.name_lines.add(rel)
        for g, ks in d.get("reactions", {}).items():
            if g.startswith("_"):
                continue
            for k, ls in ks.items():
                if k.startswith("_"):
                    continue
                for i, ln in enumerate(ls, 1):
                    rel = f"reactions/{g}/{k}/{i:02d}"
                    self.text[rel] = txt(ln)
                    mark(rel, ln)
                    if isinstance(ln, dict) and "v_neutral" in ln:
                        self.name_lines.add(rel)

    # ------------------------------------------------------------ friendship
    def _rec(self, actor, met=0):
        r = self.st.get(actor)
        if r is None:
            r = self.st[actor] = {"p": min(START + 6 * int(met or 0), 59), "day": None, "today": 0}
        return r

    def points(self, actor):
        return self._rec(actor)["p"]

    def level(self, actor):
        return level_of(self.points(actor))

    def seed(self, met):
        """First run with an existing world: drivers you already met start a bit warmer."""
        for k, m in (met or {}).items():
            if k not in self.st:
                self._rec(k, (m or {}).get("count", 0))
        self.save()

    def add(self, actor, n, why=""):
        """Change friendship. Returns (old_level, new_level) when the level changed, else None."""
        if not actor or actor in ("buh",) or actor.startswith("driver."):
            return None
        r = self._rec(actor)
        if n > 0 and why:
            # повтор той же темы с тем же водителем за игровые сутки — 0 очков (защита от гринда)
            # 11.11: seen перенесён в запись актёра (bonds.json) — перезапуск рации больше не обнуляет
            # анти-гринд (Ковбой получал «встречу на трассе» на каждом старте)
            sn = r.get("seen")
            if sn is None or sn.get("day") != self.day:
                sn = r["seen"] = {"day": self.day, "topics": []}
            if why in sn["topics"]:
                return None
            sn["topics"].append(why)
        old = level_of(r["p"])
        if n > 0:
            if r.get("day") != self.day:
                r["day"], r["today"] = self.day, 0
            # 11.11: бонус первого разговора за день (+3) — первое СОДЕРЖАТЕЛЬНОЕ касание дня,
            # не «не понял / повтори / мимо» и не «просто проехал мимо» (иначе встреча на въезде
            # в зону съедала бонус до первого настоящего разговора)
            if why.split(" ")[0] not in ("dunno", "not_heard", "already", "ack", "встреча") \
                    and r.get("bonus_day") != self.day:
                r["bonus_day"] = self.day
                n += 3                           # first talk of the (game) day
            n = max(0, min(n, DAY_CAP - r["today"]))
            r["today"] += n
        r["p"] = max(0, min(255, r["p"] + n))
        self.save()
        new = level_of(r["p"])
        if n:
            self.log(f"  дружба: {actor} {'+' if n > 0 else ''}{n} ({why}) = {r['p']}, {LEVELS[new][1]}")
        return (old, new) if new != old else None

    def save(self):
        try:
            self.path.write_text(json.dumps(self.st, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    @staticmethod
    def key(rel):
        """Audio rel path -> phrases key: drops "variants/<v>/" and "level3/"."""
        rel = re.sub(r"^variants/[^/]+/", "", rel or "")
        return rel[7:] if rel.startswith("level3/") else rel

    def introduced(self, actor):
        """Представился ли актёр игроку полным именем (ритуал перехода в lv2, 1.34)."""
        return bool(self._rec(actor).get("introduced"))

    def mark_introduced(self, actor):
        r = self._rec(actor)
        if not r.get("introduced"):
            r["introduced"] = True
            self.save()

    def calls_by_name(self, rel):
        return self.key(rel) in self.name_lines

    def lv_ok(self, actor, rel):
        """Реплика с полем "lv" звучит с этого уровня дружбы и выше, с "lvm" — не выше (уровневые пакеты).
        Без обоих полей — всем. Битые значения в phrases-файле пропускаются (как без полей)."""
        need = self.lv.get(self.key(rel)) if rel else None
        if need is None:
            return True
        lo, hi = need
        lv = self.level(actor)
        return (lo is None or lv >= lo) and (hi is None or lv <= hi)

    # ------------------------------------------------------------ mood
    def set_world(self, game_minute=None, night=False, rain=False):
        if game_minute is not None:
            day = int(game_minute // 1440)
            if self.day is not None and day != self.day:
                old = self.day
                for r in self.st.values():
                    if r.get("p", 0) > 0 and r.get("day") != old:
                        r["p"] -= 1                    # сутки без разговора с ним: −1, не ниже 0
                self.save()
            self.day = day
            self.hour = (game_minute % 1440) / 60.0
        self.night, self.rain = bool(night), bool(rain)

    # 2026-11-06 (user): mood can be raised and lowered. Steps: grumpy < tired < calm < cheerful.
    # Rudeness -2, thanks / praise / «расскажи анекдот» / «спой» +1; drifts back to the day's mood one step per 10 min.
    ORDER = ["grumpy", "tired", "calm", "cheerful"]
    DRIFT_S = 600

    def _shift(self, actor):
        import time
        v, t = getattr(self, "shift", {}).get(actor, (0, 0.0))
        steps = int((time.monotonic() - t) // self.DRIFT_S) if v else 0
        if steps:
            v = max(0, v - steps) if v > 0 else min(0, v + steps)
            self.shift[actor] = (v, time.monotonic())
        return v

    def nudge(self, actor, d, why=""):
        """Raise (+) or lower (-) the actor's mood. Returns (before, after) when the mood changed, else None."""
        import time
        if not actor or actor == "buh" or actor.startswith("driver."):
            return None
        if not hasattr(self, "shift"):
            self.shift = {}
        before = self.mood(actor)
        v = self._shift(actor)
        self.shift[actor] = (max(-3, min(3, v + d)), time.monotonic())
        after = self.mood(actor)
        if after != before:
            self.log(f"  настроение: {actor} {MOODS[before]['name']} → {MOODS[after]['name']} ({why})")
            return before, after
        return None

    def mood(self, actor):
        base = self._day_mood(actor)
        if not base:
            return None
        i = max(0, min(3, self.ORDER.index(base) + self._shift(actor)))
        return self.ORDER[i]

    def _day_mood(self, actor):
        if not actor or actor == "buh" or actor.startswith("driver."):
            return None
        h = int(hashlib.md5(f"{actor}|{self.day}".encode()).hexdigest(), 16)
        r = (h % 1000) / 1000.0
        ch, ca, ti, gr = getattr(self, "temper", TEMPER).get(actor, TEMPER_DEFAULT)
        base = "cheerful" if r < ch else "calm" if r < ch + ca else "tired" if r < ch + ca + ti else "grumpy"
        r2 = ((h // 1000) % 1000) / 1000.0
        if self._late(actor) and base in ("cheerful", "calm") and r2 < 0.4:
            base = "tired"
        if self.rain and base == "calm" and r2 > 0.7 and gr > 0:   # кто хмурым не бывает — и в дождь не хмурится
            base = "grumpy"
        return base

    def _late(self, actor):
        """Tired time: the last third of the driver's OWN shift (for the night shift the night is a working day).
        No schedule known -> the old rule: at night."""
        sc = getattr(self, "sched", {}).get(actor)
        hour = getattr(self, "hour", None)
        if not sc or hour is None:
            return self.night
        length = (sc[1] - sc[0]) % 24 or 24
        return (hour - sc[0]) % 24 >= length * 2 / 3

    def weight(self, actor, rel):
        """How much the actor's mood favours this recorded line: 3 = fits, 0.4 = the opposite, 1 = neutral."""
        m = self.mood(actor)
        k = self.key(rel)
        lm = getattr(self, "line_moods", {}).get(k) or line_mood(self.text.get(k, ""))
        if not m or not lm:
            return 1.0
        if lm == m:
            return 3.0
        if lm in OPPOSITE.get(m, set()):
            return 0.4
        return 1.0

    def chip(self, actor):
        """Short suffix for the stream overlay: hearts + mood emoji."""
        m = self.mood(actor)
        return (HEARTS[self.level(actor)] + (" " + MOODS[m]["emoji"] if m else "")).strip()

    def sulk_s(self, actor, base_s):
        """How long he keeps quiet after rudeness: a grumpy one longer, a cheerful one / a friend shorter."""
        m = self.mood(actor)
        k = {"grumpy": 1.4, "tired": 1.1, "calm": 1.0, "cheerful": 0.6}.get(m, 1.0)
        if self.level(actor) >= 3:
            k *= 0.7
        return base_s * k
