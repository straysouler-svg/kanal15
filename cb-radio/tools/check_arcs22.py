# -*- coding: utf-8 -*-
# Мок-тест arcs_tick 22.11: очередь сцены, крючки, «было кофе», фазы поломок, news_followup.
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cb_radio as cb  # noqa: E402


class FakePlayer:
    def __init__(self):
        self.played = []
    def file(self, path, actor=None, replay=False):
        self.played.append((actor, Path(path).parent.name, Path(path).name))
        return "ok"
    def idle(self, sec):
        return True


class FakeDeck:
    def __init__(self, allowed):
        self.allowed = set(allowed)
        self.on_air = set()
    @staticmethod
    def offline(a):
        return False


class FakeOp:
    pending = None
    waiting = None


class FakeWorld:
    def __init__(self, game_min=600.0):
        self.game_min = game_min
        self.arcs = {}
        self.saved = 0
    def save(self):
        self.saved += 1


orig_player, orig_random = cb.PLAYER, cb.random.random
fp = FakePlayer()
cb.PLAYER = fp
ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print("OK", name)


try:
    cfg = {"arcs_pilot": True}
    w = FakeWorld()
    deck = FakeDeck({"bahti", "sova", "stas", "mihalych"})

    # 1. дренж KOFE_Q: сцена идёт по очереди, актёр на месте
    cb.KOFE_Q[:] = [(time.monotonic() - 1, "bahti", "kofe_scene", 0)]
    cb.arcs_tick(cfg, w, deck, FakeOp(), "driving", False, 100.0, 0.0)
    check("дренж сцены", any(p[1] == "kofe_scene" and p[2] == "01.wav" for p in fp.played))
    check("очередь убыла", not cb.KOFE_Q)

    # 2. крючок-рыба: играет при счётчике 0, затем кулдаун
    fp.played.clear()
    cb._kofe_hook_at[0] = 0.0
    cb.arcs_tick(cfg, w, deck, FakeOp(), "driving", False, 100.0, 0.0)
    check("крючок сыграл", fp.played and fp.played[-1][1] == "kofe_hook")
    fp.played.clear()
    cb.arcs_tick(cfg, w, deck, FakeOp(), "driving", False, 100.0, 0.0)
    check("крючок в кулдауне", not fp.played)

    # 3. «было кофе»: сцена вчера, сегодня новый игровой день -> играет
    fp.played.clear()
    w2 = FakeWorld(game_min=1440.0 + 600.0)
    w2.arcs = {"kofe": {"n": 4, "scene": True, "after_day": 0, "after_done": False}}
    cb._kofe_after_at[0] = 0.0
    cb.arcs_tick(cfg, w2, deck, FakeOp(), "driving", False, 100.0, 0.0)
    check("«было кофе»", fp.played and fp.played[-1][1] == "kofe_after")
    check("флаг after_done", w2.arcs["kofe"]["after_done"] is True)

    # 4. поломка: фазы 0->3 играют по порядку, после 3-й цикл закрывается
    fp.played.clear()
    cb.random.random = lambda: 0.1            # форсируем старт
    w3 = FakeWorld()
    cb._next_break.clear()
    cb.BREAKDOWN.clear()
    cb.arcs_tick(cfg, w3, deck, FakeOp(), "driving", False, 100.0, 0.0)
    check("поломка началась (knock)", fp.played and fp.played[-1][1] == "mihalych" and fp.played[-1][2] == "01.wav")
    cb.BREAKDOWN["mihalych"]["until"] = 0.0   # форсируем переходы фаз
    cb.arcs_tick(cfg, w3, deck, FakeOp(), "driving", False, 100.0, 0.0)
    check("фаза stretch", fp.played[-1][2] == "02.wav")
    cb.BREAKDOWN["mihalych"]["until"] = 0.0
    cb.arcs_tick(cfg, w3, deck, FakeOp(), "driving", False, 100.0, 0.0)
    check("фаза service", fp.played[-1][2] == "03.wav")
    cb.BREAKDOWN["mihalych"]["until"] = 0.0
    cb.arcs_tick(cfg, w3, deck, FakeOp(), "driving", False, 100.0, 0.0)
    check("фаза fixed", fp.played[-1][2] == "04.wav")
    cb.BREAKDOWN["mihalych"]["until"] = 0.0
    cb.arcs_tick(cfg, w3, deck, FakeOp(), "driving", False, 100.0, 0.0)
    check("цикл закрыт", "mihalych" not in cb.BREAKDOWN)
    cb.random.random = orig_random

    # 5. news_followup: новость вчера, сегодня +1 день -> продолжение того же актёра
    fp.played.clear()
    w4 = FakeWorld(game_min=1440.0 + 700.0)
    w4.arcs = {"news_day": {"stas": 0}}
    cb._next_followup[0] = 0.0
    cb.random.random = lambda: 0.1
    cb.arcs_tick(cfg, w4, deck, FakeOp(), "driving", False, 100.0, 0.0)
    check("news_followup", fp.played and fp.played[-1][1] == "stas")
    check("news_done", "stas" in w4.arcs["news_done"])
    cb.random.random = orig_random

    # 6. флаг выключен — тишина
    fp.played.clear()
    cb.arcs_tick({"arcs_pilot": False}, w4, deck, FakeOp(), "driving", False, 100.0, 0.0)
    check("пилот выключен — молчит", not fp.played)

    # 7. ГЕЙТ драфта §2.2: поломки Бороды — только после его новости-продолжения про Мусю
    fp.played.clear()
    cb.random.random = lambda: 0.1
    cb._next_break.clear()
    cb.BREAKDOWN.clear()
    w5 = FakeWorld()
    deck_b = FakeDeck({"boroda", "yanek"})
    cb.arcs_tick(cfg, w5, deck_b, FakeOp(), "driving", False, 100.0, 0.0)
    check("до новости про Мусю — Борода без поломки", "boroda" not in cb.BREAKDOWN)
    check("остальные без гейта — Янек поломился", "yanek" in cb.BREAKDOWN)
    cb.BREAKDOWN.clear()
    fp.played.clear()
    w5.arcs = {"boroda_musya_news": True}
    cb._next_break.clear()
    cb._next_break["yanek"] = cb._next_break.get("yanek", 0.0)
    cb.arcs_tick(cfg, w5, deck_b, FakeOp(), "driving", False, 100.0, 0.0)
    check("после новости про Мусю — Борода поломился", "boroda" in cb.BREAKDOWN)
    cb.random.random = orig_random
finally:
    cb.PLAYER = orig_player
    cb.random.random = orig_random
    cb.KOFE_Q[:] = []
    cb.BREAKDOWN.clear()
    cb._next_break.clear()
print(f"ALL {ok} OK")
