"""Фотопортреты 17 водителей «Канала 15» с их грузовиками (стиль выбран 2026-11-07: только фото).
make_portraits.py [takes=2] [ключи через запятую]  -> portraits/<key>_<n>.png, журнал make_portraits.log
Сорока не рисуется (голос Татьяны — не для публичного)."""
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "cb-radio" / "tools"))
import gen_image  # noqa: E402

STYLE = ("Photorealistic cinematic photograph, 50mm lens, shallow depth of field, natural skin texture, realistic "
         "lighting and materials, editorial portrait of a European long-haul truck driver next to his or her truck. ")
RULES = (" The truck is a modern European cab-over semi tractor that is completely UNBADGED: no brand emblem, no grille "
         "logo, no model name, no lettering on the cab. No text, no letters, no numbers, no logos or brand names anywhere "
         "in the picture: plain clothes without prints or writing, unbranded objects, unreadable or no licence plates. "
         "Vertical composition, the person and the truck both clearly visible. No watermark.")

D = {
    "mihalych": "Nikolai 'Mikhalych', a 56-year-old Russian veteran trucker with thirty years on the road: weathered kind "
        "face, grey moustache, deep smile lines, old flat cap, faded checked shirt with rolled sleeves. He stands by an old "
        "early-2000s burgundy truck with a sun-faded stripe on the door and a small carved wooden cross hanging from the "
        "mirror, a bundle of fishing rods in his hand. Quiet lakeside parking at early morning, mist over the water.",
    "stas": "Stas, a 24-year-old skinny Russian trucker and wannabe video blogger: cap backwards, hoodie, earbuds, excited "
        "grin, filming himself on a smartphone held on a selfie stick, a half-eaten hot dog in the other hand. Behind him a "
        "green truck with a crooked home-made watermelon-slice sticker on the cab, a ring light visible through the "
        "windscreen. Busy truck stop at noon, crates of fruit nearby.",
    "yanek": "Yan 'Yanek', a 45-year-old calm Belarusian timber-truck driver and beekeeper: broad shoulders, short "
        "light-brown beard, knitted wool beanie, flannel shirt, quiet half-smile, holding a glass jar of golden honey. "
        "Behind him a timber truck loaded with logs and a folded hydraulic log crane. Forest road at morning, pine trees, "
        "soft mist and sun rays.",
    "lastochka": "Valentina 'Lastochka' (Swallow), a 47-year-old confident Russian woman trucker: stylish short light "
        "hair, neat make-up, manicured nails, arms crossed, sharp teasing smirk, denim shirt. Behind her a spotless white "
        "truck with small flowers on the dashboard behind the windscreen and an embroidered cushion with a swallow on the "
        "seat. Sunny truck stop, she is clearly the boss here.",
    "boroda": "Igor 'Boroda' (Beard), a 38-year-old loud, boastful Russian trucker and ex amateur rally driver: huge bushy "
        "dark beard, sunglasses pushed up on his head, roaring laugh, rolled-up sleeves, proudly holding up a thick "
        "folder stuffed with traffic fine papers like a trophy. Behind him a dark grey truck with a white refrigerated "
        "trailer, a big CB antenna on the cab, window wide open. Highway lay-by in bright afternoon sun.",
    "student": "Lyosha 'Student', a 20-year-old nervous rookie trucker on his very first trip: slim, neat haircut, slightly "
        "too big new work jacket, unsure hopeful smile, holding a stack of plastic food containers from his mom, phone in "
        "hand showing an incoming call. Behind him an almost new white truck with two navigation devices mounted on the "
        "windscreen. Big truck parking at dusk, he looks a bit lost but proud.",
    "professor": "Arkady 'Professor', a 52-year-old former history teacher turned trucker: round glasses, neat grey beard, "
        "tweed jacket over a knitted sweater, sitting on the cab step reading a thick old book with a pencil behind his "
        "ear, gently amused expression. Behind him a dark blue truck, a small bookshelf with old books visible through the "
        "side window. Quiet parking near an old European town square with a monument, warm evening light.",
    "petrovna": "Zinaida 'Petrovna', a 56-year-old plump, cheerful Russian woman trucker who spent thirty years as a train "
        "carriage attendant: rosy cheeks, warm motherly smile, knitted cardigan, holding a plate of home-made pies wrapped "
        "in a towel and a glass of tea in a classic metal railway glass holder. Behind her a light blue truck with white "
        "lace curtains in the cab windows like a train compartment. Sunny morning truck stop.",
    "ten": "Seryoga 'Ten' (Shadow), a 33-year-old mysterious night-shift trucker and quiet philosopher: lean, stubble, tired "
        "thoughtful eyes, dark hooded jacket, holding a paper cup of coffee, a steel flip lighter clicking open in the other "
        "hand. Behind him a matte black truck almost dissolving into the night. Empty night highway lay-by under orange "
        "sodium lamps, light rain on the asphalt, a hare sitting far away in the headlight beam.",
    "vitek": "Vitek, a 29-year-old trucker desperately late for his brother's wedding: white dress shirt half-tucked, suit "
        "trousers, no tie, hair a mess, phone pressed to his ear, panicking and laughing at once. A suit in a garment bag "
        "hangs in the open door of his bright red truck, a shoe box on the seat. Morning highway fuel station, motion and "
        "hurry in the air.",
    "sova": "Galina 'Sova' (Owl), a 52-year-old warm, calm Russian woman night-shift trucker and former librarian: glasses "
        "on a beaded chain, soft knitted shawl, gentle sleepy smile, holding a thermos cup of chamomile tea and a small "
        "old poetry book. Behind her an older cosy truck with warm yellow light glowing inside the cab and a plaid "
        "blanket on the seat. Quiet parking at night under a starry sky.",
    "palych": "Oleg 'Palych', a 50-year-old former traffic police officer turned night-shift trucker: stocky, short grey "
        "haircut, thick moustache, upright posture, plain civilian jacket, a police-style whistle on his key ring, a "
        "self-ironic smirk, a thermos and neat sandwiches on the step. Behind him a silver truck with a small radio scanner "
        "glowing on the dashboard. Night highway, blurred blue emergency lights passing far in the background.",
    "kardan": "Gena 'Kardan', a 41-year-old Russian night-shift trucker and former rock musician: shoulder-length messy dark "
        "hair with grey streaks, stubble, PLAIN black t-shirt with no print, worn denim vest with blank patches, leather "
        "wristbands, sitting on the cab step playing an unbranded electric guitar with a blank headstock, grinning, full of "
        "energy. Behind him a dark red truck with big speakers visible in the cab. Truck stop parking at night with string "
        "lights, warm glow.",
    "lisa": "Alyona 'Lisa' (Fox), a 34-year-old sly and cheerful Russian woman night-shift trucker, former nightclub "
        "manager: fiery copper-red hair, foxy smile, leather jacket, leaning on the door of her bright orange truck with a "
        "fox-fur tail charm hanging from the mirror. Night fuel station, colourful neon reflections on wet asphalt.",
    "rustam": "Rustam 'Samarkand', a 48-year-old Uzbek trucker from Samarkand, former wedding-hall chef: stocky, warm "
        "dignified face, trimmed black moustache with grey, embroidered black-and-white Uzbek doppa skullcap, apron over his "
        "shirt, stirring a huge cast-iron kazan of steaming plov over a gas burner, ceramic tea bowls (piala) nearby, "
        "welcoming smile. Behind him a spotless white truck. Truck stop at golden hour, steam and warm light. Respectful, "
        "no caricature.",
    "bahti": "Bakhtiyar 'Kovboy' (Cowboy), a 27-year-old Uzbek trucker who dreams of driving trucks in America: young, "
        "energetic, big grin, brown cowboy hat, wireless headphones around his neck, smartphone in hand, plain football "
        "scarf in white and green without writing, thumbs up. Behind him a brand-new glossy blue truck. Sunny highway "
        "parking. Respectful, no caricature.",
    "vera": "Vera 'Kinolog', a 41-year-old former rescue-service dog handler turned trucker: short practical dark hair, "
        "calm firm gaze, a faint dry smile, dark green fleece jacket, one hand resting on the head of an old German "
        "shepherd dog with a greying muzzle who sits loyally beside her. Behind them a dark green truck with a dog bed "
        "visible on the sleeper bunk. Dawn at a quiet roadside, cool blue light turning golden.",
}

out_dir = HERE / "portraits"
out_dir.mkdir(exist_ok=True)
takes = int(sys.argv[1]) if len(sys.argv) > 1 else 2
keys = sys.argv[2].split(",") if len(sys.argv) > 2 else list(D)
lock = threading.Lock()
total = [0.0]
log = (HERE / "make_portraits.log").open("a", encoding="utf-8")


def one(job):
    key, n = job
    out = out_dir / f"{key}_{n}.png"
    if out.exists():
        return
    for attempt in range(3):
        try:
            data, cost = gen_image.generate(STYLE + D[key] + RULES, "4:5")
            out.write_bytes(data)
            with lock:
                total[0] += cost or 0
                log.write(f"{out.name} {len(data) // 1024} KB ${cost:.3f}\n")
                log.flush()
            return
        except BaseException as e:  # gen_image raises SystemExit on API errors
            with lock:
                log.write(f"{out.name} попытка {attempt + 1}: ОШИБКА {e}\n")
                log.flush()


jobs = [(k, n) for k in keys for n in range(1, takes + 1)]
with ThreadPoolExecutor(4) as ex:
    list(ex.map(one, jobs))
log.write(f"итого за запуск ${total[0]:.3f}\nDONE\n")
log.close()
