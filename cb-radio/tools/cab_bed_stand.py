# -*- coding: utf-8 -*-
"""Стенд cab_bed (25.11, модель «магнитола слышна только под тангентой»).

Контракт утверждённого эталона (build/listen_kardan_bed_demo6.wav):
1. гейт открыт ТОЛЬКО на длительность передачи; между репликами — тишина (target 0);
2. курсор трека непрерывен: между репликами одного актёра курсор ПРОДОЛЖАЕТ идти (магнитола
   играет в паузах, тангенту слышит её только под передачей);
3. курсор per-actor: у Веры своя магнитола и свой курсор (с нуля), не курсор Кардана;
4. уровень: в буфер запечён BED_LEVEL = 0.159/0.95;
5. цепочка обработки применена (buffer отличается от сырого трека).

Плюс офлайн-рендер сверки: build/cab_bed_engine_check.wav (план как в демо-эталоне).

Запуск из корня: build\\venv\\Scripts\\python.exe -X utf8 cb-radio/tools/cab_bed_stand.py
Вердикт одной строкой, код 0/1.
"""
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WS / "cb-radio"))
sys.path.insert(0, str(WS / "cb-radio" / "tools"))

import numpy as np  # noqa: E402

import cab_bed  # noqa: E402


class _FakeBed:
    """Тот же интерфейс, что у cab_bed._Bed, без звукового устройства (headless)."""
    def __init__(self):
        self.gain = 0.0
        self.target = 0.0
        self.muted = False


class _FakePlayer:
    playing = False
    cfg = {"volume": 0.8}


def main():
    import json
    actors = json.loads((WS / "cb-radio/phrases/level3_eleven.json").read_text(encoding="utf-8"))["actors"]
    cab_bed._Bed = _FakeBed
    cab_bed.init(_FakePlayer(), actors)
    cab_bed.start_watchdog()

    fails = []

    def wait(sec):
        """Симуляция времени: гейт живёт по monotonic (реальный сон), курсор крутим сами
        (в headless нет аудио-колбека — магнитола «играет» только через _pump)."""
        cab_owner = cab_bed.owner()
        if cab_owner:
            with cab_bed._lock:
                cab = cab_bed._state["cabs"].get(cab_owner)
            if cab is not None:
                for _ in range(int(sec * 20)):
                    cab_bed._pump(cab, 2400)
        time.sleep(sec)

    def check(name, cond):
        print(("  ок   " if cond else "  FAIL ") + name)
        if not cond:
            fails.append(name)

    # 1) пять реплик Кардана — один владелец, гейт открывается
    for _ in range(5):
        cab_bed.line("kardan", 0.6)
        wait(0.05)
    ev = [t for _, t in cab_bed.events()]
    check("5 реплик Кардана: владелец kardan", cab_bed.owner() == "kardan")
    check("первый контакт = switch:kardan, дальше tx", "switch:kardan" in ev and ev.count("tx:kardan") == 4)
    wait(0.05)
    bed = cab_bed._state["stream"]
    check("во время передачи гейт открыт (target 1)", bed is not None and bed.target == 1.0)

    # 2) тишина между репликами: после окончания передачи гейт закрывается
    wait(1.0)
    check("между репликами тишина (target 0)", cab_bed._state["stream"].target == 0.0)
    check("при этом курсор продолжил идти (магнитола играет)",
          cab_bed.cabs()["kardan"]["pos"] > 0)

    # 3) курсор НЕПРЕРЫВЕН: вторая серия реплик продолжает тот же курсор
    pos_before = cab_bed.cabs()["kardan"]["pos"]
    cab_bed.line("kardan", 0.5)
    wait(0.1)
    pos_mid = cab_bed.cabs()["kardan"]["pos"]
    cab_bed.line("kardan", 0.5)
    wait(0.1)
    check("курсор не сбросился между сериями реплик", cab_bed.cabs()["kardan"]["pos"] > pos_mid > pos_before)

    # 4) смена говорящего: у Веры своя магнитола со своим курсором (с нуля)
    cab_bed.line("vera", 0.5)
    wait(0.1)
    cabs = cab_bed.cabs()
    check("у Веры своя магнитола", "vera" in cabs)
    check("курсор Веры стартует с нуля, не с курсора Кардана",
          cabs["vera"]["pos"] <= cabs["kardan"]["pos"] and cabs["vera"]["pos"] < 48000 * 2)

    # 5) проезжий без позывного — эмбиент-магнитола foreign
    cab_bed.line(None, 0.5)
    check("проезжий: владелец foreign", cab_bed.owner() == "foreign")

    # 6) уровень и цепочка запечены в буфер
    kbuf_ok = False
    with cab_bed._lock:
        kb = cab_bed._state["cabs"]["kardan"]["buf"]
        peak = float(np.max(np.abs(kb)))
        kbuf_ok = 0.05 < peak <= 0.22          # BED_LEVEL=0.167 от пика трека; пик после цепочки плавает по трекам
    check(f"уровень беда ~0.159/0.95 (пик {peak:.3f})", kbuf_ok)
    with cab_bed._lock:
        raw = cab_bed._music_raw("rock_kardan", abs(hash(("kardan", "rock_kardan"))) % 2**32)
    check("цепочка применена (буфер != сырой трек)",
          raw is not None and not np.allclose(raw[: len(kb)], kb, atol=1e-4))

    # 7) офлайн-рендер сверки с эталоном (план как в демо)
    dst = WS / "build/cab_bed_engine_check.wav"
    cab_bed.render_check(dst, [("pause", 1.0), ("kardan", 3.0), ("pause", 2.0),
                               ("kardan", 3.5), ("pause", 1.5), ("vera", 2.5)])
    check(f"офлайн-рендер сверки записан ({dst.name})", dst.exists() and dst.stat().st_size > 100000)

    print("СТЕНД КРАСНЫЙ:" if fails else "СТЕНД ЗЕЛЁНЫЙ — «магнитола только под тангентой», курсоры непрерывны")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
