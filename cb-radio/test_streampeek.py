# -*- coding: utf-8 -*-
"""Мок-тесты streampeek.py (пилот stream_viewers_pilot) — без сети: fetch подменяется,
состояние — временный файл. События: zero -> first -> record -> дедуп/гистерезис -> bet.

  py -3 -m pyflakes cb-radio/streampeek.py cb-radio/test_streampeek.py
  build/venv/Scripts/python.exe -X utf8 cb-radio/test_streampeek.py
"""
import importlib.util
import random
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_mod():
    spec = importlib.util.spec_from_file_location("streampeek", HERE / "streampeek.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_env(mod, tmp, seed=123):
    logs = []
    st_f = Path(tmp) / "viewers_state.json"
    mod.STATE_F = st_f                       # session_start/save_state не должны писать в живой файл!
    st = mod.session_start({"seed": seed}, now=0.0)
    st["bet_done"] = True                    # bet тестируем отдельно; здесь — только first/record/zero
    mod.save_state(st)
    return logs, st_f


def seq(mod, st_f, logs, values, t0=10000.0):
    """Гоняет tick с подменённым fetch по очереди значений, now растёт на POLL_EVERY_S."""
    out = []
    it = iter(values)
    now = t0                 # с запасом больше ZERO_COOL_S (baseline last_zero=0)

    def fetch(log):
        return next(it)
    for _ in values:
        out.append(mod.tick(now=now, log=logs.append, state_f=st_f, fetch=fetch))
        now += mod.POLL_EVERY_S
    return out


def test_cycle(tmp):
    mod = load_mod()
    logs, st_f = make_env(mod, tmp)
    # эфир начался: первый положительный -> first; планка поднимается только со STEP
    ev = seq(mod, st_f, logs, [5, 7, 0, 0, 0, 3, 9, 2])
    assert ev[0] == "first", ev          # None->5 (планка озвучена первой)
    assert ev[1] is None, ev             # 7 < 5+3 — молчим (гистерезис шага)
    assert ev[2] == "zero", ev           # 7 -> 0
    assert ev[3] is None and ev[4] is None, ev   # zero чаще чем раз в 30 мин не звучит
    assert ev[5] == "first", ev          # 0 -> 3 после тишины
    assert ev[6] == "record", ev         # 3 -> 9: планка 5+3=8 <= 9 — record
    assert ev[7] is None, ev             # 9 -> 2: ничего
    print("1) first/record/zero/дедуп: OK", ev)

    # гистерезис рекорда: рост по +1 — record звучит только когда счётчик вырос на STEP от планки
    logs.clear()
    ev = seq(mod, st_f, logs, [10, 11, 12, 13, 14, 15, 16, 17], t0=20000.0)
    assert ev == [None, None, "record", None, None, "record", None, None], ev
    print("2) гистерезис рекорда: OK", ev)


def test_bet_once(tmp):
    st_f = Path(tmp) / "viewers_state.json"
    bet_count = 0
    for seed in range(200):
        mod = load_mod()
        mod.STATE_F = st_f                   # пишем во временный state, не в живой
        st = mod.session_start({"seed": seed}, now=0.0)
        rnd = random.Random(seed)
        bets = 0
        now = 0.0
        for viewers in ([5, 10, 0, 4, 12, 0, 7, 20, 30, 0, 9, 40, 50, 60]):
            now += 400.0                     # больше всех кулдаунов
            ev = mod.decide(st, viewers, now, rnd, lambda m: None)
            if ev == "bet":
                bets += 1
        bet_count += bets
        assert bets <= 1, (seed, bets)       # раз на сессию — жёстко
    assert bet_count > 0                     # но иногда звучит (шанс 0.35)
    print(f"3) bet: не чаще раза на сессию (200 сессий, bet сработал {bet_count} раз): OK")


def test_no_stream_no_event(tmp):
    mod = load_mod()
    logs, st_f = make_env(mod, tmp)
    ev = seq(mod, st_f, logs, [None, None, None])   # активного эфира нет
    assert ev == [None, None, None], ev
    print("4) нет эфира -> событий нет: OK")


def main():
    with tempfile.TemporaryDirectory() as td:
        test_cycle(td)
    with tempfile.TemporaryDirectory() as td:
        test_bet_once(td)
    with tempfile.TemporaryDirectory() as td:
        test_no_stream_no_event(td)
    print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ: 4/4")


if __name__ == "__main__":
    main()
