"""Правка готовой групповой сцены: убрать эмблемы с грузовиков, добавить надутого Бороду.
fix_group.py party_2 party_3 ...  -> group/<name>_fix.png, журнал make_group.log"""
import base64
import sys
from pathlib import Path

import make_group

EDIT = ("Edit this photograph, keep EVERYTHING else exactly the same (composition, people, trucks, colours, light, "
        "camera angle, resolution). Changes: 1) remove every brand emblem, logo, badge, diagonal grille bar and any "
        "lettering from ALL trucks - grilles become plain, unbadged; also remove any text on clothes. "
        "2) The big man with the huge bushy dark beard stands with his arms firmly crossed and a comically pouting, "
        "offended face, looking away, while everyone else keeps cheering and waving.")

HERE = Path(__file__).resolve().parent
with (HERE / "make_group.log").open("a", encoding="utf-8") as log:
    for name in sys.argv[1:]:
        src = HERE / "group" / f"{name}.png"
        ref = "data:image/png;base64," + base64.b64encode(src.read_bytes()).decode()
        try:
            data, cost = make_group.generate(EDIT, ref, "16:9", "1K", intro=False)
        except BaseException as e:
            data, cost = None, 0
            log.write(f"{name}_fix: ОШИБКА {e}\n")
        if data:
            (HERE / "group" / f"{name}_fix.png").write_bytes(data)
            log.write(f"{name}_fix.png ${cost:.3f}\n")
        log.flush()
    log.write("FIXDONE\n")
