# -*- coding: utf-8 -*-
"""Мок-тесты волны 2 streampeek.py (чат/подписчики/superchat/питч) — без сети: fetch подменяется,
состояние — временный файл. Питч: кулдауны 15-18 мин, «щедрость глушит economy», after_donation.

  py -3 -m pyflakes cb-radio/streampeek.py cb-radio/test_pitch.py
  build/venv/Scripts/python.exe -X utf8 cb-radio/test_pitch.py
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


def env(mod, tmp, seed=7):
    logs = []
    st_f = Path(tmp) / "viewers_state.json"
    mod.STATE_F = st_f                       # ничего не пишем в живой state
    # session_start с реалистичным now (как monotonic у live) — метки «сейчас», не 0.0
    st = mod.session_start({"seed": seed}, now=100000.0)
    mod.save_state(st)
    return logs, st_f


def chat_fetch(broadcast_id, messages):
    """fetch(endpoint, params): liveBroadcasts -> id эфира, videos -> activeLiveChatId, дальше сообщения."""
    state = {"msgs": list(messages)}

    def f(endpoint, params):
        if endpoint == "liveBroadcasts":
            return {"items": [{"id": "B1", "snippet": {"liveChatId": broadcast_id}}]}
        if endpoint == "videos":
            return {"items": [{"liveStreamingDetails": {"activeLiveChatId": broadcast_id}}]}
        return {"items": [{"snippet": {"textMessageText": m}} for m in state["msgs"].pop(0)]}
    return f


def test_chat(tmp):
    mod = load_mod()
    logs, st_f = env(mod, tmp)
    f = chat_fetch("LC1", [
        ["привет"],                     # тик 1: first
        ["а", "б", "в", "г", "д"],      # тик 2: active (5 >= 4)
        [], [], [],                     # тик 3-5: тишина
        [], [], [],                     # ещё тишина
    ])
    now = 100000.0
    ev1 = mod.chat_tick(now=now, log=logs.append, state_f=st_f, fetch=f)
    assert ev1 == "first", ev1
    ev2 = mod.chat_tick(now=now + mod.CHAT_POLL_EVERY_S, log=logs.append, state_f=st_f, fetch=f)
    assert ev2 == "active", ev2
    # зрителей нет -> quiet не звучит
    ev3 = mod.chat_tick(now=now + 2 * mod.CHAT_POLL_EVERY_S + mod.CHAT_QUIET_AFTER_S,
                        log=logs.append, state_f=st_f, fetch=f)
    assert ev3 is None, ev3
    # зрители появились, тишина длинная -> quiet
    st = mod.load_state()
    st["viewers"] = 8
    mod.save_state(st)
    ev4 = mod.chat_tick(now=now + 3 * mod.CHAT_POLL_EVERY_S + mod.CHAT_QUIET_AFTER_S + 10,
                        log=logs.append, state_f=st_f, fetch=f)
    assert ev4 == "quiet", ev4
    # тот же тик снова quiet не звучит (кулдаун 40 мин)
    ev5 = mod.chat_tick(now=now + 3 * mod.CHAT_POLL_EVERY_S + mod.CHAT_QUIET_AFTER_S + 20,
                        log=logs.append, state_f=st_f, fetch=f)
    assert ev5 is None, ev5
    assert any("liveChatId получен" in s for s in logs)
    print("1) чат first/active/quiet: OK")


def test_chat_snippet_fallback(tmp):
    """27.11: videos.list без activeLiveChatId (эфир без чата) -> фолбэк snippet.liveChatId; разрешение id идёт."""
    mod = load_mod()
    logs, st_f = env(mod, tmp)

    def f(endpoint, params):
        if endpoint == "liveBroadcasts":
            return {"items": [{"id": "B1", "snippet": {"liveChatId": "LC_SNIPPET"}}]}
        if endpoint == "videos":
            return {"items": [{"liveStreamingDetails": {}}]}    # activeLiveChatId отсутствует
        return {"items": []}
    ev = mod.chat_tick(now=100000.0, log=logs.append, state_f=st_f, fetch=f)
    assert ev is None, ev
    st = mod.load_state()
    assert st["chat_id"] == "LC_SNIPPET", st
    print("2) чат: фолбэк snippet.liveChatId: OK")


def test_subs(tmp):
    mod = load_mod()
    logs, st_f = env(mod, tmp)
    seq = iter([110, 111, 113, 114])
    f = lambda endpoint, params: {"items": [{"statistics": {"subscriberCount": str(next(seq))}}]}
    now = 100000.0
    assert mod.subs_tick(now=now, log=logs.append, state_f=st_f, fetch=f) is None   # база 110
    ev = mod.subs_tick(now=now + mod.SUBS_POLL_EVERY_S, log=logs.append, state_f=st_f, fetch=f)
    assert ev == "subs", ev
    # прирост есть, но кулдаун 30 мин
    ev = mod.subs_tick(now=now + 2 * mod.SUBS_POLL_EVERY_S, log=logs.append, state_f=st_f, fetch=f)
    assert ev is None, ev
    ev = mod.subs_tick(now=now + mod.SUBS_MIN_GAP_S + mod.SUBS_POLL_EVERY_S,
                       log=logs.append, state_f=st_f, fetch=f)
    assert ev == "subs", ev
    print("2) подписчики: база/прирост/кулдаун 30 мин: OK")


def test_superchat(tmp):
    mod = load_mod()
    logs, st_f = env(mod, tmp)
    batch = [{"id": "sc1", "snippet": {"amountMicros": "1000000"}},
             {"id": "sc2", "snippet": {"amountMicros": "2000000"}}]
    f = lambda endpoint, params: {"items": list(batch)}
    assert mod.superchat_tick(now=0.0, log=logs.append, state_f=st_f, fetch=f) == "superchat"
    assert mod.superchat_tick(now=300.0, log=logs.append, state_f=st_f, fetch=f) is None   # дедуп
    batch.append({"id": "sc3", "snippet": {}})
    assert mod.superchat_tick(now=600.0, log=logs.append, state_f=st_f, fetch=f) == "superchat"
    print("3) superchat: дедуп по id, новый -> событие: OK")


def test_pitch_cycle(tmp):
    mod = load_mod()
    logs, st_f = env(mod, tmp, seed=3)        # session_start(now=100000), метки «сейчас»
    rnd = random.Random(3)
    T0 = 100000.0
    # баг 2 (20.11): первые 15 минут стрима — НИКАКОГО питча (economy/norm/vnd)
    assert mod.pitch_tick(now=T0 + 60, log=logs.append, state_f=st_f, rnd=rnd) is None
    assert mod.pitch_tick(now=T0 + 899, log=logs.append, state_f=st_f, rnd=rnd) is None
    # первый питч — economy на штатном интервале: кандидат с 15-й минуты, заслон
    # pitch_last=«старт эфира» + полный гэп 15-18 мин -> звучит 18:00 от включения
    ev = mod.pitch_tick(now=T0 + 1080, log=logs.append, state_f=st_f, rnd=rnd)
    assert ev == "economy", ev
    # заслон: сразу повтор невозможен
    assert mod.pitch_tick(now=T0 + 1081, log=logs.append, state_f=st_f, rnd=rnd) is None
    # «щедрость»: донат 30 с назад глушит economy/vnd (окно after_donation ещё не наступило);
    # norm в этом шаге не должна подменять — уводим её таймер
    mod.note_donation(now=T0 + 1300, state_f=st_f)
    st = mod.load_state()
    st.update(pitch_economy_next=T0 + 1320, pitch_last=T0 + 300, pitch_norm_next=T0 + 10 ** 9)
    mod.save_state(st)
    ev = mod.pitch_tick(now=T0 + 1330, log=logs.append, state_f=st_f, rnd=rnd)
    assert ev is None, ev
    assert any("щедрости" in s for s in logs), logs
    # after_donation: окно 60-120 с после НОВОГО доната; бросок фиксируем (< P) — детерминизм
    mod.note_donation(now=T0 + 2000, state_f=st_f)
    st = mod.load_state()
    st.update(after_roll=0.1, pitch_norm_next=T0 + 10 ** 9, pitch_economy_next=T0 + 10 ** 9)
    mod.save_state(st)
    ev = mod.pitch_tick(now=T0 + 2080, log=logs.append, state_f=st_f, rnd=rnd)
    assert ev == "after_donation", ev
    assert mod.pitch_tick(now=T0 + 2140, log=logs.append, state_f=st_f, rnd=rnd) is None
    print("4) питч: старт не раньше 15 мин/заслон/щедрость/after_donation: OK")


def test_pitch_norm_and_viewers(tmp):
    mod = load_mod()
    logs, st_f = env(mod, tmp, seed=11)
    rnd = random.Random(11)
    now = 100000.0
    # viewers_no_donations: зрителей >=5, донатов не было >=20 мин
    st = mod.load_state()
    st.update(viewers=9, donation_last=now - mod.PITCH_NO_DON_AFTER_S - 60,
              pitch_economy_next=0.0, pitch_last=0.0)
    mod.save_state(st)
    ev = mod.pitch_tick(now=now, log=logs.append, state_f=st_f, rnd=rnd)
    assert ev == "viewers_no_donations", ev
    # norm: ~45 мин от старта
    ev = mod.pitch_tick(now=now + mod.PITCH_GAP_MIN_S + 200, log=logs.append, state_f=st_f, rnd=rnd)
    assert ev in ("economy", "norm", "viewers_no_donations"), ev   # любой легальный питч, но звучит не чаще заслона
    st = mod.load_state()
    st.update(pitch_last=0.0, pitch_economy_next=now + 10 ** 9, pitch_norm_next=now - 1)
    mod.save_state(st)
    ev = mod.pitch_tick(now=now + mod.PITCH_GAP_MIN_S + 300, log=logs.append, state_f=st_f, rnd=rnd)
    assert ev == "norm", ev
    print("5) питч: viewers_no_donations/norm: OK")


def main():
    with tempfile.TemporaryDirectory() as td:
        test_chat(td)
    with tempfile.TemporaryDirectory() as td:
        test_chat_snippet_fallback(td)
    with tempfile.TemporaryDirectory() as td:
        test_subs(td)
    with tempfile.TemporaryDirectory() as td:
        test_superchat(td)
    with tempfile.TemporaryDirectory() as td:
        test_pitch_cycle(td)
    with tempfile.TemporaryDirectory() as td:
        test_pitch_norm_and_viewers(td)
    print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ: 6/6")


if __name__ == "__main__":
    main()
