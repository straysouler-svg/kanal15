#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Офлайн-стенд рации «бот-игрок» (этап A, промт prompts/offline_sim_2026-11-15.md).

Без игры, без звука, в ускоренном времени: FakeGame едет по маршруту world.roads.path(),
RecPlayer вместо звука пишет (время, актёр, файл, текст), бот подаёт текст прямо в
Operator._decide(). Часы виртуальные: time.monotonic/time.time/time.sleep подменены
во всём процессе (стенд — отдельный процесс, рация не запускается).

Живое состояние не трогаем: state.json / quest_state.json / world_state.json / bonds.json
копируются в build/sim/<seed>/ и константы путей переключаются на копии ДО создания объектов.
Лог рации пишется в build/sim/run_seed<N>.log, нарушения — build/sim/violations_seed<N>.txt;
код возврата != 0, если есть нарушения уровня fail.

Запуск (venv coop-buddy: нужны numpy/sounddevice/soundfile для import cb_radio):
  G:\\Claude\\coop-buddy\\.venv\\Scripts\\python.exe -X utf8 tools/sim_drive.py \
      --seed 7 --route helsinki:oulu --minutes 120 --script sim/basic.json

Не проверяется здесь (честно): реальная телеметрия, задержки звука, микрофон и whisper,
ощущение темпа, фоновая болтовня (живёт в цикле main() — это этап B), проезжие-иностранцы
(пишут временные wav в ROOT), «заметка:» пишет в ПЕСОЧНИЦУ через прослойку open().
"""
import argparse
import builtins
import json
import random
import re
import shutil
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # cb-radio/
sys.path.insert(0, str(ROOT))

GAME_SPEED = 17.5        # игровое время / реальное (урок ноября №1: из телеметрии ~17-19)
PLAYER_SPEED = 22.0      # м/с (~80 км/ч)
GAME_MIN0 = 600.0        # старт в 10:00 игрового — день, водители активны

# ---------- виртуальные часы (подменяем ДО import cb_radio, чтобы все модули взяли их) ----------
_vt = [1_000.0]          # виртуальный monotonic, сек
_wt0 = [time.time()]     # реальная отметка старта: time() = _wt0 + (monotonic - 1000)
_decide_zone = [None]    # снимок deck.allowed на момент ПОСЛЕДНЕГО _decide (гонка решение↔звук, ревью 15.11)


def _vnow():
    return _vt[0]


def _vtime():
    return _wt0[0] + (_vt[0] - 1_000.0)


def _vsleep(s):
    _vt[0] += max(0.0, s)


def advance(s):
    _vt[0] += s


time.monotonic = _vnow                                   # noqa: — стенд, отдельный процесс
time.time = _vtime                                       # noqa:
time.sleep = _vsleep                                     # noqa:

import cb_radio as cb                                    # noqa: E402
import world as world_mod                                # noqa: E402
import bonds as bonds_mod                                # noqa: E402
import overlay as overlay_mod                            # noqa: E402  (только карта rel->текст, сервер не стартует)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--route", default="helsinki:oulu", help="город:город (токены map/cities_full.json)")
    ap.add_argument("--minutes", type=float, default=120, help="игровых минут езды")
    ap.add_argument("--script", default="sim/basic.json")
    ap.add_argument("--start-min", type=float, default=GAME_MIN0,
                    help="игровая минута старта (600 = 10:00); смены водителей зависят от неё")
    ap.add_argument("--corpus", default="sim/corpus_log.json",
                    help="корпус настоящих фраз из cb_radio.log; между шагами сценария бот говорит оттуда")
    ap.add_argument("--corpus-every", type=float, default=55, help="средний интервал корпусных фраз, сек")
    ap.add_argument("--corpus-all", action="store_true",
                    help="прогнать весь корпус по разу, без повторов (ревью Клода 15.11)")
    ap.add_argument("--seeds", default="",
                    help="пакет прогонов «1-20» или «1,2,3»: каждый зерном в своём процессе, сводка в build/sim/seeds_summary.txt")
    args = ap.parse_args()

    if args.seeds:
        # пакетный режим: отдельный процесс на зерно (состояние не протекает между прогонами)
        import subprocess
        seeds = []
        for part in args.seeds.split(","):
            if "-" in part:
                a, b = part.split("-", 1)
                seeds.extend(range(int(a), int(b) + 1))
            elif part.strip():
                seeds.append(int(part))
        results = {}
        for s in seeds:
            cmd = [sys.executable, "-X", "utf8", str(Path(__file__)), "--seed", str(s),
                   "--route", args.route, "--minutes", str(args.minutes), "--script", args.script,
                   "--corpus", args.corpus, "--corpus-every", str(args.corpus_every),
                   "--start-min", str(args.start_min)]
            if args.corpus_all:
                cmd.append("--corpus-all")
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            tail = (r.stdout or "").strip().splitlines()
            results[s] = (r.returncode, tail[-1] if tail else "(нет вывода)")
            print(f"seed {s}: код {r.returncode} :: {results[s][1]}", flush=True)
        ok = sum(1 for rc, _ in results.values() if rc == 0)
        # доля «для» по каждому зерну: < 45% — подстановка имён сломана, пакет FAIL (ревью 15.11, 2-й круг)
        import re as _re2
        zone_bad = {}
        for s in seeds:
            vf = ROOT.parent / "build" / "sim" / f"violations_seed{s}.txt"
            if vf.exists():
                m = _re2.search(r"доля для: ([0-9.]+)", vf.read_text(encoding="utf-8"))
                if m and float(m.group(1)) < 0.45:
                    zone_bad[s] = float(m.group(1))
        summ = ROOT.parent / "build" / "sim" / "seeds_summary.txt"
        summ.parent.mkdir(parents=True, exist_ok=True)
        with open(summ, "w", encoding="utf-8") as f:
            f.write(f"# пакет {args.seeds} ({args.route}, {args.minutes} игр.мин)\n")
            for s, (rc, line) in results.items():
                mark = "OK" if rc == 0 else "FAIL"
                if s in zone_bad:
                    mark = f"FAIL (доля «для» {zone_bad[s]:.0%} < 45%)"
                f.write(f"seed {s}: {mark} :: {line}\n")
            f.write(f"\nзелёных: {ok}/{len(seeds)}")
            if zone_bad:
                f.write(f"; подстановка имён сломана у зёрен: {sorted(zone_bad)}")
            f.write("\n")
        print(f"пакет окончен: зелёных {ok}/{len(seeds)}, сводка {summ.name}")
        return 0 if ok == len(seeds) and not zone_bad else 1

    random.seed(args.seed)

    # ---------- песочница состояния ----------
    sand = ROOT.parent / "build" / "sim" / f"seed{args.seed}"
    sand.mkdir(parents=True, exist_ok=True)
    copies = {}
    for name in ("state.json", "quest_state.json", "world_state.json", "bonds.json"):
        src = ROOT / name
        if src.exists():
            dst = sand / name
            shutil.copy2(src, dst)
            copies[name] = dst
    cb.STATE_FILE = copies.get("state.json", sand / "state.json")
    cb.QUEST_FILE = copies.get("quest_state.json", sand / "quest_state.json")
    cb.VITYOK_QUEST_STATE = cb.QUEST_FILE
    world_mod.STATE = copies.get("world_state.json", sand / "world_state.json")
    run_log = ROOT.parent / "build" / "sim" / f"run_seed{args.seed}.log"
    cb.LOG_FILE = run_log
    cb.ERR_FILE = sand / "errors.log"
    cb.ARC_FILE = sand / "archive.log"

    # «Заметка: …» пишет ROOT/"notes.log" через встроенный open — перенаправляем в песочницу
    real_open = builtins.open

    def sandbox_open(file, *a, **kw):
        p = Path(str(file))
        if p.name == "notes.log" and p.parent == cb.ROOT:
            file = str(sand / "notes.log")
        return real_open(file, *a, **kw)
    cb.open = sandbox_open

    run_log.write_text("", encoding="utf-8")
    _game_ref = [None]         # FakeGame появится ниже; игровое время в каждой строке журнала (ревью Клода 15.11)
    _real_log = cb.log

    def _sim_log(msg, ch=None, tb=None):
        g = _game_ref[0]
        if g is not None:
            msg = f"[сим {int(g.game_min) % 1440 // 60:02d}:{int(g.game_min) % 60:02d}] {msg}"
        _real_log(msg, ch, tb)

    log = cb.log = _sim_log

    # ---------- состав ----------
    cfg = cb.load_cfg()
    acts = json.loads(cb.PHRASES_JSON.read_text(encoding="utf-8"))["actors"]
    overlay_mod.load_texts(cb.PHRASES_JSON, "")
    text_of = overlay_mod._TEXT

    deck = cb.Deck()
    world = world_mod.World(cfg, acts)
    if not world.ok:
        print("КРИТ: карта не загрузилась (map/cities_full.json)")
        return 2
    cb.BONDS = bonds_mod.Bonds(copies.get("bonds.json", sand / "bonds.json"), cb.PHRASES_JSON, log)
    bonds = cb.BONDS

    # ---------- FakeGame: едем по маршруту ----------
    city_a, city_b = (args.route.split(":") + [""])[:2]
    if city_a not in world.cities:
        near = min(world.cities, key=lambda c: abs(len(c) - len(city_a)))
        print(f"КРИТ: город «{city_a}» не найден (похожий: {near}); токены — map/cities_full.json")
        return 2
    if city_b not in world.cities:
        print(f"КРИТ: город «{city_b}» не найден")
        return 2

    class FakeGame:
        """Телеметрия без игры: грузовик едет по цепочке городов с PLAYER_SPEED м/с."""

        def __init__(self, w, a, b, start_min):
            self.w = w
            self.route = w.roads.path(a, b) or [a, b]
            self.seg = 0
            self.x, self.z = w.roads.xz(self.route[0])
            self.game_min = start_min
            self.paused = False

        def step(self, dt):                                   # dt — виртуальные секунды
            self.game_min += dt * GAME_SPEED / 60.0
            if self.paused or self.seg + 1 >= len(self.route):
                if self.seg + 1 >= len(self.route):           # доехали — новая случайная цель
                    dest = random.choice(list(self.w.cities))
                    nxt = self.w.roads.path(self.route[-1], dest)
                    if nxt:
                        self.route, self.seg = nxt, 0
                return
            ax, az = self.w.roads.xz(self.route[self.seg])
            bx, bz = self.w.roads.xz(self.route[self.seg + 1])
            import math
            seg_len = math.hypot(bx - ax, bz - az) or 1.0
            remain = math.hypot(bx - self.x, bz - self.z)
            move = PLAYER_SPEED * dt
            if move >= remain:
                self.x, self.z, self.seg = bx, bz, self.seg + 1
            else:
                k = move / seg_len
                self.x, self.z = self.x + (bx - ax) * k, self.z + (bz - az) * k

        def state(self, require_engine=False):
            return "paused" if self.paused else "driving"

        def pos(self):
            return self.x, self.z, int(self.game_min)

        def wipers(self):
            return False

        def lights_high(self):
            return False

    game = FakeGame(world, city_a, city_b, args.start_min)
    _game_ref[0] = game
    world.set_job(city_b)

    # ---------- RecPlayer: вместо звука — записи ----------
    played = []            # dict(t, actor, rel, text, dur, lvl, allowed)

    class RecPlayer:
        """Полный дублёр Player по атрибутам, которые читает Operator (без звука)."""

        def __init__(self):
            self.last_speaker, self.last_t = None, 0.0
            self.last_said = None
            self.said, self.said_n = {}, 0
            self.spoke, self.voices = set(), 0
            self.playing, self.speaker = False, None
            self.guest_dist = None
            self.cfg, self.game, self.world, self.ptt = cfg, game, world, None

        def file(self, path, actor=None, replay=False):
            path = str(path)
            if not path.startswith("_") and not Path(path).name.startswith(("kerchunk_", "enter_")):
                vp = cb.variant_of(Path(path))
                if vp is None:                       # обращения, которых нет в варианте сборки
                    return "error"
                path = str(vp)
            rel = cb._rel(Path(path)) if not path.startswith("_") else path
            try:
                import soundfile as sf
                dur = sf.info(path).duration if Path(path).exists() else 2.0
            except Exception:
                dur = 2.0
            lvl = bonds.level(actor) if actor and bonds else None
            played.append({
                "t": round(_vnow(), 1), "actor": actor, "rel": rel, "replay": bool(replay),
                "text": text_of.get(rel, ""), "dur": round(dur, 2), "lvl": lvl,
                "allowed": sorted(deck.allowed) if deck.allowed is not None else None,
                "far": sorted(deck.allowed_far),
                "d_zone": sorted(_decide_zone[0]) if _decide_zone[0] is not None else None,
            })
            log(f"[сим] эфир: {actor or '—'} :: {rel} :: {text_of.get(rel, '')[:70]}")
            if actor and not replay:
                self.said_n += 1
                self.said[actor] = (path, self.said_n)
                self.last_said = actor
                self.spoke.add(actor)
            advance(dur)                               # виртуальные часы сдвигаются на длину реплики
            self.last_speaker, self.last_t = actor, _vnow()
            return "ok"

        def idle(self, sec):
            advance(sec)
            return True

        def street(self, data, sr, actor=None):
            self.file("street", actor)

        def stop(self):
            pass

    cb.PLAYER = RecPlayer()

    op = cb.Operator(deck, None)
    op.world, op.game = world, game

    # ---------- сценарий и корпус ----------
    script_path = Path(args.script)
    if not script_path.is_absolute():
        script_path = ROOT / script_path
    steps = json.loads(script_path.read_text(encoding="utf-8"))["steps"] if script_path.exists() else []
    corpus_path = Path(args.corpus)
    if not corpus_path.is_absolute():
        corpus_path = ROOT / corpus_path
    corpus = []
    if corpus_path.exists():
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    elif (ROOT / "cb_radio.log").exists():
        # первый прогон: собрать корпус настоящих фраз игрока из журнала
        rx = re.compile(r"тангента: «(.+?)»")
        for line in (ROOT / "cb_radio.log").read_text(encoding="utf-8", errors="replace").splitlines():
            m = rx.search(line)
            if m and len(m.group(1)) > 4:
                corpus.append(m.group(1))
        corpus = sorted(set(corpus))
        corpus_path.parent.mkdir(exist_ok=True)
        corpus_path.write_text(json.dumps(corpus, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"[сим] корпус из cb_radio.log: {len(corpus)} фраз -> {corpus_path}")

    # ---------- корпус: мешок без повторов + подстановка имён (ревью Клода 15.11) ----------
    # Позывные для подстановки (именительный): имя в фразе корпуса заменяется на актуальное
    NAME_FORMS = {"mihalych": "Михалыч", "stas": "Стас", "yanek": "Янек", "lastochka": "Ласточка",
                  "boroda": "Борода", "soroka": "Сорока", "student": "Студент", "professor": "Профессор",
                  "petrovna": "Петровна", "ten": "Тень", "vitek": "Витёк", "sova": "Сова", "ment": "Палыч",
                  "kardan": "Кардан", "lisa": "Лиса", "rustam": "Самарканд", "bahti": "Ковбой", "vera": "Вера"}
    import intents as _int

    def _name_word_i(text):
        """Индекс первого слова-имени водителя в фразе (или None)."""
        cur = _int.addressee(text)
        if not cur:
            return None, None
        stems = sorted((s.replace("ё", "е").strip() for s in _int.NAMES[cur]), key=len, reverse=True)
        for i, w in enumerate(text.split()):
            nw = _int.norm(w).strip()          # 15.11 (2-й круг): norm() обрамляет пробелами —
            if any(nw.startswith(s) for s in stems):   # startswith без strip никогда не матчил,
                return i, cur                          # подстановка молча не работала
        return None, cur

    def substitute_name(text, actor):
        i, cur = _name_word_i(text)
        if i is None or cur == actor:
            return text
        words = text.split()
        w = words[i]
        words[i] = NAME_FORMS[actor] + w[len(w.rstrip(",.!?…:")):]
        return " ".join(words)

    def drop_name(text):
        i, cur = _name_word_i(text)
        if i is None:
            return text
        words = [w for j, w in enumerate(text.split()) if j != i]
        out = " ".join(words).lstrip(" ,—-")
        return (out[:1].upper() + out[1:]) if out else text

    corpus_bag = []
    corpus_done = [False]       # --corpus-all: мешок опустел -> корпус больше не звучит

    def next_corpus():
        if not corpus_bag:
            if args.corpus_all:
                corpus_done[0] = True
                return None
            corpus_bag.extend(corpus)
            random.shuffle(corpus_bag)
        text = corpus_bag.pop()
        # подстановка: ~60% — водитель из зоны, ~25% — отсутствующий, ~15% — имя убираем
        if _int.addressee(text):
            r = random.random()
            here = sorted(deck.allowed or ())
            away = [a for a in NAME_FORMS if a not in (deck.allowed or ())]
            if r < 0.60 and here:
                text = substitute_name(text, random.choice(here))
            elif r < 0.85 and away:
                text = substitute_name(text, random.choice(away))
            else:
                text = drop_name(text)
        return text


    stop_list = []
    stop_path = ROOT / "sim" / "canon_stop.json"
    if stop_path.exists():
        stop_list = json.loads(stop_path.read_text(encoding="utf-8"))

    # ---------- нарушения ----------
    viol = []
    missed = {}            # фраза -> сколько раз ответили dunno/not_heard (топ-20 в сводке, ревью 15.11)

    def fail(rule, msg):
        viol.append({"level": "FAIL", "rule": rule, "t": round(_vnow(), 1), "msg": msg})
        log(f"[сим] НАРУШЕНИЕ {rule}: {msg}")

    def note(rule, msg):
        viol.append({"level": "note", "rule": rule, "t": round(_vnow(), 1), "msg": msg})
        log(f"[сим] заметка {rule}: {msg}")

    hooks_used = {}        # actor -> count (правило 5)
    last_rel = None        # правило 7
    lvl_seen = {}          # actor -> последний уровень (правило 8)
    zone_stat = {}         # корпусные фразы: «для» (в зоне) / «про» (вне зоны) / «без имени» (2-й круг 15.11)

    def check_played(step_desc, who, is_q, greetq, expect_silence, window):
        """Правила 1-10 к записям эфира в окне после фразы бота."""
        nonlocal last_rel
        for r in window:
            rel, actor, txt = r["rel"], r["actor"], (r["text"] or "").lower()
            if rel is None:
                continue               # street/шумовые события вне AUDIO_ROOT — контентные правила не для них
            # 7: один и тот же файл не звучит дважды подряд (кроме «повтори» — replay по запросу;
            # /lane/ — честный ответ по маршруту: не переехал — та же реплика, ревью 15.11)
            if rel == last_rel and not rel.startswith("_") and not r["replay"] and "/lane/" not in rel:
                fail(7, f"файл дважды подряд: {rel} ({step_desc})")
            last_rel = rel
            # 6: отвечает только тот, кто в зоне; «дальний по имени» (3.2) и сцена гудка (свои
            # честные дистанции 150–1500 м) — по замыслу (ревью 15.11)
            if actor and actor != who and "/horn/" not in rel and not r["replay"] \
                    and r["allowed"] is not None and actor not in r["allowed"] \
                    and actor not in r["far"] and not rel.startswith("street"):
                fail(6, f"отвечает {actor} вне зоны {r['allowed']} (+far {r['far']}) ({step_desc})")
            # 6б (ревью Клода 15.11): ответ из far НЕ адресатом — различаем гонку:
            # в зоне при решении -> уехал между решением и звуком (норма, note);
            # вне зоны уже при решении -> FAIL. replay («повтори») — сервис, по запросу.
            elif actor and actor != who and "/horn/" not in rel and not r["replay"] \
                    and r["allowed"] is not None and actor in r["far"]:
                if r["d_zone"] is not None and actor in r["d_zone"]:
                    note(6, f"{actor} уехал между решением и звуком — норма ({step_desc})")
                elif r["d_zone"] is not None:
                    fail(6, f"{actor} отвечает из far, но при решении уже был вне зоны ({step_desc})")
            # 2: спросили по имени — отвечает только он (who/absent-ответы ок; cross — второй голос
            # по отношениям, horn — отложенная сцена гудка, knows — про третьего, отвечают другие; 15.11)
            if who and actor and actor != who and "who" not in rel and "absent" not in rel \
                    and "/player/" not in rel and "/cross/" not in rel and "/horn/" not in rel \
                    and "/knows/" not in rel:
                fail(2, f"спросили {who}, отвечает {actor}: {rel} ({step_desc})")
            # 3: вопрос — никогда «принял» (replay по «повтори» — по запросу, ок)
            if is_q and "/player/ack/" in rel and not r["replay"]:
                fail(3, f"«принял» на вопрос: {rel} ({step_desc})")
            # 5: зацепки — не чаще одной на актёра; не после уклончивого ответа
            if "/hooks/" in rel:
                hooks_used[actor] = hooks_used.get(actor, 0) + 1
                if hooks_used[actor] > 1:
                    fail(5, f"вторая зацепка за сессию от {actor} ({step_desc})")
                idx = played.index(r)
                if idx and "/evade" in played[idx - 1]["rel"]:
                    fail(5, f"зацепка сразу после уклончивого ответа ({step_desc})")
            # 9: канон стоп-лист
            for st in stop_list:
                if st["actor"] != "*" and st["actor"] != actor:
                    continue
                if actor in st.get("except", []):
                    continue
                for w_ in st["words"]:
                    if w_.lower() in txt:
                        fail(9, f"канон: {actor} сказал «{w_}»: {txt[:60]} ({step_desc})")
        # уровни дружбы не прыгают через ступень
        for r in window:
            a = r["actor"]
            if a and r["lvl"] is not None:
                if a in lvl_seen and abs(r["lvl"] - lvl_seen[a]) > 1:
                    fail(8, f"уровень {a} прыгнул {lvl_seen[a]} -> {r['lvl']} ({step_desc})")
                lvl_seen[a] = r["lvl"]
        # 4: «привет + вопрос» — должен прозвучать ответ на вопрос
        if greetq and window and all("greet" in r["rel"] for r in window):
            fail(4, f"«привет+вопрос» съеден приветствием ({step_desc})")
        if expect_silence and window:
            fail(2, f"ожидалась тишина (служебная реплика), прозвучало: "
                    f"{[r['rel'] for r in window]} ({step_desc})")
        # 10: позвали по имени того, кто в зоне, — а в ответ тишина (не провал)
        if who and not window:
            note(10, f"тишина на обращение к {who} ({step_desc})")

    def run_bot_phrase(text, who=None, is_q=None, greetq=False, expect_silence=False, desc="",
                       expect_rel=None, forbid_rel=None, expect_answer=False):
        import intents
        if is_q is None:
            is_q = intents.is_question(text)
        if who is None:
            # 15.11 (ревью Клода): адресат из текста — иначе «дальний по имени» (3.2) ловил FAIL по правилу 6б
            who = intents.addressee(text)
        # счётчик «для/про/без имени» по корпусным фразам (ревью 15.11, 2-й круг)
        if desc == "корпус":
            key = ("для" if who in (deck.allowed or ()) else "про") if who else "без имени"
            zone_stat[key] = zone_stat.get(key, 0) + 1
        log(f"[сим] бот: «{text}»" + (f" (кто: {who})" if who else ""))
        t0 = len(played)
        _decide_zone[0] = set(deck.allowed) if deck.allowed is not None else None
        bonds0 = {a: r["p"] for a, r in bonds.st.items()} if bonds else {}
        try:
            op._decide(text, False, None, _vnow(), True)
        except Exception:
            fail(1, f"исключение в _decide: {traceback.format_exc(limit=3)}")
            return
        # ждём ответ: pending/due + проигрывание
        guard = 0
        while guard < 300:
            if op.due():
                try:
                    op.answer()
                except Exception:
                    fail(1, f"исключение в answer: {traceback.format_exc(limit=3)}")
                    break
            elif not op.pending:
                break
            advance(0.5)
            guard += 1
        # 11 (ревью Клода 15.11): фраза БЕЗ обращения не должна ронять дружбу на ≥15
        # (прецедент: анекдот с матом давал −25 как за оскорбление)
        if bonds:
            for a, r in bonds.st.items():
                drop = bonds0.get(a, r["p"]) - r["p"]
                if drop >= 15:
                    if not who:
                        fail(11, f"дружба {a} −{drop} от фразы без обращения: «{text[:50]}»")
                    elif a != who:
                        note(11, f"дружба {a} −{drop}, хотя обращение было к {who}: «{text[:50]}»")
        window = played[t0:]
        step_desc = desc or text[:40]
        # 12 (ревью Клода 15.11): явные ожидания сценария — expect_rel/forbid_rel/expect_answer
        if expect_rel and not any(expect_rel in (r["rel"] or "") for r in window):
            fail(12, f"ожидали «{expect_rel}» в ответе, прозвучало: "
                     f"{[r['rel'] for r in window]} ({step_desc})")
        if forbid_rel and any(forbid_rel in (r["rel"] or "") for r in window):
            fail(12, f"запрещённое «{forbid_rel}» прозвучало ({step_desc})")
        if expect_answer and not window:
            fail(12, f"ожидался ответ, а в эфире тишина ({step_desc})")
        if any(r["rel"] and ("/player/dunno/" in r["rel"] or "/player/not_heard/" in r["rel"]) for r in window):
            missed[text] = missed.get(text, 0) + 1
        check_played(step_desc, who, is_q, greetq, expect_silence, window)

    # ---------- главный цикл ----------
    log(f"[сим] старт: seed={args.seed} маршрут={args.route} {args.minutes} игр.мин, "
        f"сценариев={len(steps)}, корпус={len(corpus)}")
    end_vmin = game.game_min + args.minutes
    step_i = 0
    wait_since = None
    next_corpus_t = _vnow() + args.corpus_every
    last_prog = game.game_min

    while game.game_min < end_vmin:
        dt = 1.0
        game.step(dt)
        world.update(game.x, game.z, dt, game.game_min)
        deck.allowed = set(world.inside)
        deck.allowed_far = set(world.far())
        for k in world.entered:
            deck.prefer.add(k)
            log(f"[сим] в зоне: {k}")
        for k in world.left:
            deck.left_at[k] = _vnow()
            log(f"[сим] вышел из зоны: {k}")
        bonds.set_world(world.game_min, world.is_night(world.game_min), False)
        if game.game_min - last_prog >= 60:
            last_prog = game.game_min
            log(f"[сим] игровой час {(int(game.game_min) % 1440) // 60:02d}:{int(game.game_min) % 60:02d}, "
                f"в зоне {len(deck.allowed)}")

        # шаги сценария: summon призывает водителя (world.summon — 2 км позади, сразу в зоне),
        # when_inside ждёт его (таймаут 900 вирт.с — пропуск)
        if step_i < len(steps):
            st = steps[step_i]
            if "set_min" in st:                       # скачок игровых часов (смены, ночь)
                game.game_min = st["set_min"]
                log(f"[сим] игровое время -> {st['set_min'] / 60:.1f} ч")
            if "text" not in st:                      # служебный шаг (только set_min)
                step_i += 1
                continue
            need = st.get("when_inside") or st.get("summon")
            if st.get("summon") and st["summon"] not in deck.allowed and not st.get("_summoned"):
                st["_summoned"] = True                # один вызов на шаг, не спамить каждый тик
                got = world.summon(st["summon"])
                log(f"[сим] summon {st['summon']}: {got or 'не вышел (не смена?)'}")
            if "bond" in st:                          # выставить очки дружбы (уровни 0/1/2, ревью 15.11)
                for a_, p_ in st["bond"].items():
                    bonds._rec(a_)["p"] = p_
                log(f"[сим] дружба выставлена: {st['bond']}")
            if "banish" in st:                        # мир увозит водителя за 60 км («только что уехал»)
                d = world.drivers.get(st["banish"])
                if d:
                    d.x, d.z = d.x + 60000, d.z + 60000
                    d.companion = False
                    world.update(game.x, game.z, 1.0, game.game_min)
                    deck.allowed = set(world.inside)
                    deck.allowed_far = set(world.far())
                    for k in world.left:
                        deck.left_at[k] = _vnow()
                    log(f"[сим] banish {st['banish']}: увезён за 60 км")
            if need is None or need in deck.allowed:
                run_bot_phrase(st["text"], st.get("who"), st.get("q"), st.get("greetq", False),
                               st.get("expect_silence", False), st.get("id", ""),
                               st.get("expect_rel"), st.get("forbid_rel"), st.get("expect_answer", False))
                step_i += 1
                wait_since = None
            else:
                # пока ждём адресата — корпус настоящих фраз тоже работает
                if corpus and _vnow() >= next_corpus_t and deck.allowed and not op.pending and not corpus_done[0]:
                    ph = next_corpus()
                    if ph:
                        run_bot_phrase(ph, None, None, desc="корпус")
                    next_corpus_t = _vnow() + random.uniform(args.corpus_every * 0.6, args.corpus_every * 1.6)
                wait_since = wait_since or _vnow()
                if _vnow() - wait_since > 900:
                    note(10, f"шаг «{st.get('id', step_i)}» пропущен: {need} не появился в зоне")
                    step_i += 1
                    wait_since = None
        elif corpus and _vnow() >= next_corpus_t and deck.allowed and not corpus_done[0]:
            ph = next_corpus()
            if ph:
                run_bot_phrase(ph, None, None, desc="корпус")
            next_corpus_t = _vnow() + random.uniform(args.corpus_every * 0.6, args.corpus_every * 1.6)
        advance(dt)

    # ---------- сводка ----------
    fails = [v for v in viol if v["level"] == "FAIL"]
    groups = {}
    for r in played:
        if r["rel"] is None:
            groups["street/noise"] = groups.get("street/noise", 0) + 1
            continue
        m = re.match(r"(?:variants/[^/]+/)?(?:audio/)?reactions/([^/]+)/([^/]+)/", r["rel"])
        key = "/".join(m.groups()) if m else r["rel"].split("/")[0]
        groups[key] = groups.get(key, 0) + 1
    log(f"[сим] финиш: реплик в эфире {len(played)}, нарушений {len(fails)}, заметок "
        f"{sum(1 for v in viol if v['level'] == 'note')}")
    log(f"[сим] ответы по группам: {json.dumps(groups, ensure_ascii=False)}")
    top_missed = sorted(missed.items(), key=lambda kv: -kv[1])[:20]
    if top_missed:
        log("[сим] топ непонятых (dunno/not_heard): "
            + "; ".join(f"«{t[:45]}» ×{n}" for t, n in top_missed))

    # корпусные фразы по адресатам: «для» — в зоне, «про» — вне зоны, «без имени» (ревью 15.11, 2-й круг)
    z_for = zone_stat.get("для", 0)
    z_named = z_for + zone_stat.get("про", 0)
    z_share = z_for / z_named if z_named else 0.0
    log(f"[сим] корпус по адресатам: для {z_for}, про {zone_stat.get('про', 0)}, "
        f"без имени {zone_stat.get('без имени', 0)}; доля «для» {z_share:.0%}")
    if z_named >= 10 and z_share < 0.45:
        note(13, f"доля «для» {z_share:.0%} < 45% — подстановка имён сломана (на пакете — FAIL)")

    vfile = ROOT.parent / "build" / "sim" / f"violations_seed{args.seed}.txt"
    with real_open(vfile, "w", encoding="utf-8") as f:
        f.write(f"# Стенд этап A, seed={args.seed}, маршрут {args.route}, {args.minutes} игр.мин\n")
        f.write(f"# реплик в эфире: {len(played)}; FAIL: {len(fails)}\n")
        f.write(f"# корпус по адресатам: для {z_for}, про {zone_stat.get('про', 0)}, "
                f"без имени {zone_stat.get('без имени', 0)}; доля для: {z_share:.2f}\n\n")
        for v in viol:
            f.write(f"[{v['level']}] правило {v['rule']} t={v['t']}: {v['msg']}\n")
        f.write(f"\n# группы ответов: {json.dumps(groups, ensure_ascii=False)}\n")
        if top_missed:
            f.write("\n# топ-20 непонятых фраз (dunno/not_heard):\n")
            for t, n in top_missed:
                f.write(f"#   ×{n} «{t}»\n")
    print(f"прогон окончен: FAIL={len(fails)} note={len(viol) - len(fails)}; "
          f"лог {run_log.name}, нарушения {vfile.name}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
