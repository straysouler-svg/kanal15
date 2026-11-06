"""Дружба и настроение водителей (2026-11-06, идея пользователя: скрытые очки дружбы с каждым водителем).

Дружба — у каждого водителя свои очки 0..255, хранятся между поездками (bonds.json рядом с рацией).
  Новый водитель начинает с 25; кто уже встречался на трассе — чуть больше.
  + разговор с ним (+1, по имени +2, «спасибо»/похвала +3), первый разговор за игровой день +3, встреча на трассе +1;
    за день с одного водителя не больше +15.  − грубость −25.
  Уровни: 0 незнакомый (<30) · 1 знакомый (30+) · 2 приятель (60+) · 3 друг (150+).
  Незнакомый не зовёт тебя по имени (реплики с обращением — только знакомым и дальше).
  Приятель и друг охотнее выходят на связь сами: делятся дорогой, погодой; друг прощает грубость быстрее.

Настроение — у каждого своё на игровой день (бодрое / спокойное / усталое / хмурое), ночью чаще устают,
в дождь чаще хмурятся. Из записанных реплик водитель чаще выбирает те, что по настроению (по тегам эмоций
ElevenLabs в тексте: [tired], [laughs], [frustrated] …). Хмурый дольше дуется на грубость, весёлый отходит быстрее."""
import hashlib
import json
import re
from pathlib import Path

LEVELS = [(0, "незнакомый"), (30, "знакомый"), (60, "приятель"), (150, "друг")]
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


def line_mood(text):
    """Which mood a recorded line sounds like (by its emotion tags), or None."""
    tg = tags_of(text)
    best, n = None, 0
    for m, d in MOODS.items():
        k = len(tg & d["tags"])
        if k > n:
            best, n = m, k
    return best


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
        for k, a in d.get("actors", {}).items():
            for i, ph in enumerate(a.get("phrases", []), 1):
                rel = f"{k}/{i:02d}"
                self.text[rel] = txt(ph)
                if isinstance(ph, dict) and "v_neutral" in ph:
                    self.name_lines.add(rel)
        for sid, ls in d.get("scenes", {}).items():
            for i, ln in enumerate(ls, 1):
                rel = f"scenes/{sid}/{i:02d}"
                self.text[rel] = txt(ln)
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
        old = level_of(r["p"])
        if n > 0:
            if r.get("day") != self.day:
                r["day"], r["today"] = self.day, 0
                n += 3                                   # first talk of the (game) day
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

    def calls_by_name(self, rel):
        return self.key(rel) in self.name_lines

    # ------------------------------------------------------------ mood
    def set_world(self, game_minute=None, night=False, rain=False):
        if game_minute is not None:
            self.day = int(game_minute // 1440)
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
        base = "cheerful" if r < 0.3 else "calm" if r < 0.65 else "tired" if r < 0.85 else "grumpy"
        r2 = ((h // 1000) % 1000) / 1000.0
        if self.night and base in ("cheerful", "calm") and r2 < 0.4:
            base = "tired"
        if self.rain and base == "calm" and r2 > 0.7:
            base = "grumpy"
        return base

    def weight(self, actor, rel):
        """How much the actor's mood favours this recorded line: 3 = fits, 0.4 = the opposite, 1 = neutral."""
        m = self.mood(actor)
        lm = line_mood(self.text.get(self.key(rel), ""))
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
