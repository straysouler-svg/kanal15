"""Оживить выбранную групповую сцену деталями, не меняя композицию.
detail_group.py <src name> <takes> [size]  -> group/<src>_live_<n>.png, журнал make_group.log"""
import base64
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import make_group

EDIT = (
    "Edit this aerial drone photograph. KEEP the composition, camera angle, every person (faces, clothes, poses, "
    "positions), the dog, every truck (shape, colour, position) and the sunny summer daylight EXACTLY as they are. "
    "Add life and many small realistic details, as a careful set dresser would:\n"
    "- Tyre tracks: flattened grass and dark muddy tyre ruts curving in from a dirt country track at the edge of the "
    "meadow to every parked truck, a little dried mud on the wheels and lower cabs.\n"
    "- Background: a bright birch grove and a mixed forest edge along the far side of the meadow, two or three lone "
    "birches near the trucks giving dappled shade; a hazy summer horizon.\n"
    "- The plov station: next to the kazan a gas cylinder with a hose under the burner, a wooden cutting board with "
    "julienned carrots and onion peels, a big sack of rice, a bottle of sunflower oil, garlic heads, a knife; on the "
    "grass beside it several plain crumpled plastic shopping bags (no logos) with carrots, onions and bread sticking out.\n"
    "- The table: pies on embroidered towels, a sliced watermelon, cucumbers and tomatoes, tea bowls and a teapot by the "
    "samovar, paper cups, a jar of honey, a cooler box underneath, a few folding camp chairs around.\n"
    "- Around the camp: an open guitar case near the rocker, a portable speaker, a dog water bowl, a towel drying on a "
    "truck mirror, a couple of cab doors open, flip-flops by a cab step, a football lying in the grass.\n"
    "- Nature and life: dandelions, clover and wild flowers in the grass, a couple of white butterflies, small swarms of "
    "midges glowing in the sunlight, two swallows in the sky, light steam rising from the plov, slight breeze in the "
    "grass, a faint trail of trodden grass behind the walking man.\n"
    "- The big man with the huge bushy dark beard stands with arms crossed and a comically offended pout, looking away, "
    "while everyone else cheers and waves.\n"
    "Photorealistic, natural colours, not oversaturated. No text, no letters, no logos or brand emblems on trucks, bags, "
    "clothes or objects, no watermark.")

HERE = Path(__file__).resolve().parent
name, takes = sys.argv[1], int(sys.argv[2])
size = sys.argv[3] if len(sys.argv) > 3 else "2K"
src = HERE / "group" / f"{name}.png"
ref = "data:image/png;base64," + base64.b64encode(src.read_bytes()).decode()
start = len(list((HERE / "group").glob(f"{name}_live_*.png")))
log = (HERE / "make_group.log").open("a", encoding="utf-8")


def one(n):
    out = HERE / "group" / f"{name}_live_{n}.png"
    for attempt in range(3):
        try:
            data, cost = make_group.generate(EDIT, ref, "16:9", size, intro=False)
            out.write_bytes(data)
            log.write(f"{out.name} {size} {len(data) // 1024} KB ${cost:.3f}\n")
            log.flush()
            return
        except BaseException as e:
            log.write(f"{out.name} попытка {attempt + 1}: ОШИБКА {e}\n")
            log.flush()


with ThreadPoolExecutor(takes) as ex:
    list(ex.map(one, range(start + 1, start + takes + 1)))
log.write("LIVEDONE\n")
log.close()
