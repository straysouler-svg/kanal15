# -*- coding: utf-8 -*-
"""Симулятор частоты стрим-пилотов: виртуальный стрим 120 мин (2 эпохи), тик раз в минуту.
Реальные функции streampeek.py (решения + журнал «почему»), моки fetch без сети,
постановка голосовых — та же логика, что в cb_radio.py (buq_q, stream_news-таймер,
заслон питча). Живой viewers_state.json не трогаем (временный файл).

  build/venv/Scripts/python.exe -X utf8 tools/sim_stream_epoch.py
  -> build/sim_stream_epoch_report.md
"""
import importlib.util
import json
import random
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("streampeek", ROOT / "streampeek.py")
sp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp)

MIN = 60.0
T0 = 100000.0          # монотонный «старт стрима»
STREAM_MIN = 120

# --- сценарий аудитории (детерминированный) ---
def viewers_at(m):
    if m < 5:
        return 0
    if m < 12:
        return 1
    if m < 20:
        return 3
    if m < 30:
        return 8
    if m == 45:
        return 19          # скачок +4
    if m < 60:
        return 15
    if m == 78:
        return 26          # скачок +4
    if m < 90:
        return 22
    return 22

CHAT_WAVES = {  # минута -> число сообщений за тик
    11: 1, 12: 6, 13: 8, 14: 5, 16: 7, 18: 6,
    45: 5, 46: 8, 47: 6, 49: 7,
    72: 1, 74: 6, 75: 8, 76: 5, 78: 7,
    100: 6, 101: 8, 102: 5, 104: 7, 105: 6,
}
DONATIONS = {35: "100 RUB", 70: "250 RUB"}            # DonationAlerts (через note_donation)
SUPERCHAT_AT = 85
SUBS_AT = {50: 111, 100: 112}                          # subscriberCount по минутам (база 110)


def make_fetches():
    def chat(endpoint, params):
        if endpoint == "liveBroadcasts":
            return {"items": [{"snippet": {"liveChatId": "LC1"}}]}
        m = cur[0]
        return {"items": [{"snippet": {"textMessageText": f"msg{i}"}} for i in range(CHAT_WAVES.get(m, 0))]}

    def subs(endpoint, params):
        n = 110
        for k in sorted(SUBS_AT):
            if cur[0] >= k:
                n = SUBS_AT[k]
        return {"items": [{"statistics": {"subscriberCount": str(n)}}]}

    def sc(endpoint, params):
        if cur[0] >= SUPERCHAT_AT:
            return {"items": [{"id": "sc1", "snippet": {"amountMicros": "500000"}}]}
        return {"items": []}

    cur = [0]
    return cur, chat, subs, sc


def norm_txt(s):
    s = re.sub(r"[\[\]()][^\[\]()]*[\[\])]", "", s)   # теги и ремарки
    return re.sub(r"\s+", " ", s).strip()[:90]


def main():
    tmp = Path(tempfile.mkdtemp())
    st_f = tmp / "viewers_state.json"
    logs = []
    rnd = random.Random(42)
    cur, chat_f, subs_f, sc_f = make_fetches()

    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    buh = data["reactions"]["buh"]

    def pool_len(kind):
        node = buh.get(kind)
        if node is None and "__" in kind:            # viewers__zero -> buh["viewers"]["zero"]
            head, sub = kind.split("__", 1)
            node = (buh.get(head) or {}).get(sub)
        if node is None:
            return 0
        return sum(len(v) for v in node.values()) if isinstance(node, dict) else len(node)

    # --- состояние «рации» (как в main()): buh-очередь, news-таймер, использованные news ---
    buh_q = []                    # (due_mono, kind)
    used_news = set()
    news_at = None
    played = []                   # хронология: (минута, kind, текст)
    counts = {}
    pitch_reasons = []

    def enqueue(minute, kind, pool_kind=None, delay=(5, 15)):
        if pool_len(pool_kind or kind) == 0:
            logs.append(f"{minute:3d} мин: пул {pool_kind or kind} пуст — не ставим")
            return
        due = T0 + minute * MIN + rnd.uniform(*delay)
        buh_q.append((due, kind))
        buh_q.sort()

    sp.STATE_F = st_f                 # session_start пишет через глобальный STATE_F — временный файл!
    sp.session_start({"seed": 42}, now=T0)
    logs.append("0 мин: стрим включён — session_start, планируем stream_greet")
    enqueue(0, "stream_greet", "stream_greet", delay=(60, 120))

    for m in range(0, STREAM_MIN + 1):
        now = T0 + m * MIN
        cur[0] = m
        # --- донаты DonationAlerts ---
        if m in DONATIONS:
            sp.note_donation(now, state_f=st_f)
            enqueue(m, "donation", "donation", delay=(30, 90))
            logs.append(f"{m:3d} мин: ДОНАТ {DONATIONS[m]} -> buh/donation + метка для питча")
        # --- зрители (раз в 5 мин, как POLL_EVERY_S) ---
        if m % 5 == 0 and m > 0:
            v = viewers_at(m)
            ev = sp.tick(now=now, log=logs.append, state_f=st_f,
                         fetch=lambda log, v=v: v)
            if ev:
                enqueue(m, f"viewers__{ev}", f"viewers__{ev}")
        # --- чат (раз в минуту; в рации 60 с) ---
        ev = sp.chat_tick(now=now, log=logs.append, state_f=st_f, fetch=chat_f)
        if ev:
            enqueue(m, f"chat__{ev}", f"chat__{ev}")
        # --- подписчики (раз в 15 мин) ---
        if m % 15 == 0 and m > 0:
            ev = sp.subs_tick(now=now, log=logs.append, state_f=st_f, fetch=subs_f)
            if ev:
                enqueue(m, "subs", "subs")
        # --- super chat (раз в 5 мин) ---
        if m % 5 == 4 and m > 0:
            ev = sp.superchat_tick(now=now, log=logs.append, state_f=st_f, fetch=sc_f)
            if ev:
                enqueue(m, "superchat", "superchat")
        # --- питч (раз в минуту) ---
        ev = sp.pitch_tick(now=now, log=logs.append, state_f=st_f, rnd=rnd)
        if ev:
            enqueue(m, f"donate_pitch__{ev}", f"donate_pitch__{ev}")
            pitch_reasons.append((m, ev))
        # --- stream_news (как в cb_radio: после 2-3 мин, интервал 15-25, каждая раз) ---
        if news_at is None and m >= 3:
            news_at = now + rnd.uniform(0, 2) * MIN
        if news_at and now >= news_at:
            pool = [i for i in range(len(buh["stream_news"])) if i not in used_news]
            if pool:
                news_at = now + rnd.uniform(15, 25) * MIN
                enqueue(m, "stream_news", "stream_news")
                logs.append(f"{m:3d} мин: stream_news — новость (неозвученных осталось {len(pool)})")
            else:
                news_at = None
                logs.append(f"{m:3d} мин: stream_news — пул иссяк, больше не звоним")
        # --- проигрывание buh_q (эфир свободен, минута >= due) ---
        while buh_q and buh_q[0][0] <= now:
            _, kind = buh_q.pop(0)
            node = buh[kind.split("__")[0]] if "__" in kind else buh[kind]
            if isinstance(node, dict):
                sub = kind.split("__")[1]
                lines = node[sub]
            else:
                lines = node
            avail = [i for i in range(len(lines))
                     if not (kind == "stream_news" and i in used_news)]
            n = rnd.choice(avail) + 1 if avail else rnd.randrange(len(lines)) + 1
            if kind == "stream_news":
                used_news.add(n - 1)
            played.append((m, kind, f"{kind}/{n:02d}", norm_txt(lines[n - 1]["text"])))
            counts[kind] = counts.get(kind, 0) + 1

    # --- отчёт ---
    out = ROOT.parent / "build" / "sim_stream_epoch_report.md"
    L = []
    L.append("# Симуляция стрим-пилотов: 120 мин (2 эпохи), зерно 42\n")
    L.append("Зрители: 0 (0-5 мин) -> 1 -> 3 -> 8 -> 15 -> +4 (45) -> 22 -> +4 (78). "
             "Чат: тишина до 10, волны 5-8/тик (12-18, 45-49, 74-78, 100-105), затишье ~25 мин между. "
             "Донаты DA: 35 мин (100), 70 мин (250). Super Chat: 85 мин. Подписчики: +1 на 50, +1 на 100.\n")
    L.append("## Хронология озвученного (время -> что сказала бухгалтерия)\n")
    L.append("| мин | пул/файл | текст |")
    L.append("|---|---|---|")
    for m, kind, f, t in played:
        L.append(f"| {m} | {f} | {t} |")
    L.append("\n## Счётчики по категориям\n")
    for k in sorted(counts):
        L.append(f"- {k}: {counts[k]}")
    L.append(f"\nВсего голосовых: {sum(counts.values())} за 2 ч (~{sum(counts.values()) / 2:.1f}/час)")
    L.append("\n## Журнал решений (звучим/молчим, причины)\n```")
    L.extend(logs)
    L.append("```\n")
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"отчёт: {out}")
    print(f"всего голосовых: {sum(counts.values())} (~{sum(counts.values()) / 2:.1f}/час)")
    for m, kind, f, t in played:
        print(f"{m:3d} мин  {f:<38} {t[:60]}")


if __name__ == "__main__":
    main()
