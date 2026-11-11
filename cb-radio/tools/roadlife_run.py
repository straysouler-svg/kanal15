"""Стенд «жизни трассы» (ступень 0): прогон 30 игровых суток ускоренно.

Без рации, без звука, на КОПИИ состояния (cb-radio/world_state.json не трогаем).
Повторяемо по зерну: --seed N (по умолчанию 7).

Выход: build/roadlife/diary_seed<N>.txt и summary_seed<N>.txt.

Запуск:  G:/Claude/gruzovichki/build/venv/Scripts/python.exe cb-radio/tools/roadlife_run.py --seed 7
"""
import argparse
import json
import math
import random
import shutil
import sys
from pathlib import Path

CB = Path(__file__).resolve().parent.parent          # cb-radio/
ROOT = CB.parent                                      # gruzovichki/
OUT = ROOT / "build" / "roadlife"
sys.path.insert(0, str(CB))

import world as world_mod                               # noqa: E402
from roadlife import Roadlife                           # noqa: E402

TICK_S = 15.0           # один тик = 5 игровых минут = 300 игровых с; на трассе время ×20
                        # (канал scale @700, design_telemetry_2026-11-11.md; 5 игр. мин = 15 настоящих с)
DAYS = 30
START_GM = 8 * 60       # старт в понедельник 08:00


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--start", type=int, default=START_GM)
    ap.add_argument("--tag", default="v2", help="суффикс выходных файлов (старые не затирать)")
    ap.add_argument("--meet-radius", type=float, default=None, help="доля радиуса рации для «встречи»")
    ap.add_argument("--rest-scale", type=float, default=1.0, help="множитель длительности стоянок")
    ap.add_argument("--pair-sync", type=float, default=0.0,
                    help="0..1: тяготение пар ур.>=3 к маршрутам друг друга (вариант живости)")
    ap.add_argument("--diminish", action="store_true",
                    help="убывающая отдача: греет первая встреча пары за сутки, повторные — доля")
    ap.add_argument("--stationary", action="store_true",
                    help="контроль: игрок стоит на месте — сколько жизни в мире без него")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)

    # --- копия состояния мира: живой world_state.json НЕ трогаем
    src_state = CB / "world_state.json"
    copy_state = OUT / f"world_state_seed{args.seed}.json"
    if src_state.exists():
        shutil.copyfile(src_state, copy_state)
    world_mod.STATE = copy_state                      # world.py пишет/читает рядом с собой — направляем на копию

    phrases = json.loads((CB / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    actors = {k: a for k, a in phrases.get("actors", {}).items() if not a.get("extra")}
    names = {k: a.get("name", k) for k, a in actors.items()}
    try:
        cfg = json.loads((CB / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}

    w = world_mod.World(cfg, actors)
    if not w.ok:
        print("world not ok: cities missing")
        sys.exit(1)
    # встречи «по заказу» игроку не нужны: жизнь водителей — сама по себе
    w.meet_every_s = 1e18
    w.quiet_s = 1e18

    rl = Roadlife(w, names, seed=args.seed, meet_radius=args.meet_radius,
                  diminishing=args.diminish)
    rl.REAL_SEC_PER_GAME_MIN = TICK_S * 60.0 / 300.0

    # --- ночные рейсы Студента (решение 11.11, только стенд): 3 ночи в месяц по зерну
    rng_nr = random.Random(args.seed + 2)
    student_nights = set(rng_nr.sample(range(1, args.days), 3))
    sd = w.drivers.get("student")
    student_sched = sd.schedule if sd else None

    # --- синтетический игрок: кольцо по крупным городам, едет 22 м/с, отдыхает ночью
    pops = {}
    try:
        raw = json.loads(world_mod.CITIES.read_text(encoding="utf-8"))
        pops = {t: c.get("population", 0) for t, c in raw.items()}
    except (OSError, ValueError):
        pass
    hubs = [t for t in w.cities if pops.get(t, 0) >= 400000]
    if len(hubs) < 8:
        hubs = sorted(w.cities, key=lambda t: -pops.get(t, 0))[:20]
    rng = random.Random(args.seed + 1)
    hub_route = rng.sample(hubs, min(len(hubs), 14))
    rl.player_mode = ("стоит на месте в стартовом городе (контрольный прогон)" if args.stationary
                      else f"кольцо по {len(hub_route)} крупным городам (случайная выборка по зерну), "
                           f"22 м/с, ночью стоянка; старт мира — копия world_state.json "
                           f"(последняя поездка пользователя)")
    px, pz = w.roads.xz(hub_route[0])
    ppath = []
    pi = 0

    def next_leg():
        nonlocal ppath, pi
        pi = (pi + 1) % len(hub_route)
        goal = hub_route[pi]
        p = w.roads.path(w.roads.nearest(px, pz), goal) or []
        ppath = list(p)

    next_leg()
    gm = float(args.start)
    rain_days = {}
    ticks = int(args.days * 1440 / 5)
    prev_rest = {k: 0.0 for k in w.drivers}
    nr_reroute_day = None                            # ночной рейс: маршрут к Тени раз в ночь
    for i in range(ticks):
        dt = TICK_S
        gm += 5.0
        night = world_mod.World.is_night(gm)
        day = int(gm // 1440)
        # ночной рейс Студента: в выбранные ночи смена «any» (едет вопреки расписанию),
        # маршрут — в сторону Тени: чтобы они оказались на одном перегоне (решение 11.11)
        if sd is not None:
            sd.schedule = "any" if day in student_nights else student_sched
            if day in student_nights and int((gm % 1440) // 60) in (20, 22, 0) \
                    and nr_reroute_day != day \
                    and sd.x is not None and sd.resting <= 0:
                td = w.drivers.get("ten")
                if td is not None and td.x is not None:
                    goal = w.roads.nearest(td.x, td.z)
                    p = w.roads.path(w.roads.nearest(sd.x, sd.z), goal)
                    if p and len(p) > 1:
                        sd.route = list(p)
                        nr_reroute_day = day
        # погода: решение о дожде — раз в сутки (иначе бросок каждый тик держит дождь почти вечно)
        day = int(gm // 1440)
        if day not in rain_days:
            rain_days[day] = rng.random() < 0.3 and rng.uniform(180, 600) or 0.0
        rain_left = rain_days[day] - (gm % 1440)
        rain = rain_left > 0
        # игрок едет; ночью — стоянка до 6:00 (контрольный прогон — стоит)
        if not args.stationary and (not night or rng.random() < 0.1):
            step = 22.0 * dt
            while step > 0 and len(ppath) > 1:
                tx, tz = w.roads.xz(ppath[1])
                rem = math.hypot(tx - px, tz - pz)
                if rem <= step:
                    px, pz = tx, tz
                    ppath.pop(0)
                    step -= rem
                else:
                    px += (tx - px) / rem * step
                    pz += (tz - pz) / rem * step
                    step = 0
            if len(ppath) <= 1:
                next_leg()
        w.update(px, pz, dt, gm)
        # стоянки подольше: свежая стоянка (resting вырос) — умножаем
        if args.rest_scale != 1.0:
            for k, d in w.drivers.items():
                if d.resting > prev_rest.get(k, 0.0):
                    d.resting *= args.rest_scale
                prev_rest[k] = d.resting
        # тяготение пар ур.>=3: отдыхающий/пустой партнёр получает рейс к городу назначения своей пары
        if args.pair_sync > 0 and i % 12 == 0 and rng.random() < args.pair_sync:
            for (a, b), lvl in rl.pairs.items():
                if lvl < 3:
                    continue
                for k, o in ((a, b), (b, a)):
                    d, od = w.drivers[k], w.drivers[o]
                    if d.x is None or od.x is None or len(od.route) < 2:
                        continue
                    if d.resting <= 0 and len(d.route) > 1:
                        continue
                    p = w.roads.path(w.roads.nearest(d.x, d.z), od.route[-1])
                    if p and len(p) > 1:
                        d.route = list(p)
                        d.resting = 0.0
                    break
        rl.student_night(gm, night)
        rl.step(gm, night, rain)

    # добиваем замеры последнего дня
    for k in names:
        rl.daily_mood[k].extend(rl._day_samples[k])

    diary_path = OUT / f"diary_seed{args.seed}_{args.tag}.txt"
    summary_path = OUT / f"summary_seed{args.seed}_{args.tag}.txt"
    debug_path = OUT / f"debug_seed{args.seed}_{args.tag}.txt"
    diary_path.write_text(rl.diary(), encoding="utf-8")
    summary_path.write_text(rl.summary(args.days, real_sec_per_game_min=TICK_S * 60.0 / 300.0),
                            encoding="utf-8")
    debug_path.write_text("\n".join(f"{rl.fmt_gm(g)}, {p}. {k} — {kind}"
                                    for g, p, kind, k in rl.debug_log) + "\n", encoding="utf-8")
    rl.save_state()
    print(f"seed={args.seed} days={args.days}: событий {len(rl.events)}, "
          f"в эфире {sum(1 for e in rl.events if e['audible'])}, "
          f"пересказ {len(rl.retold_events)}, холодков {len(rl.cold_log)}")
    print(diary_path)
    print(summary_path)


if __name__ == "__main__":
    main()
