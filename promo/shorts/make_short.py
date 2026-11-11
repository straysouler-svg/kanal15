"""УСТАРЕВШИЙ конвейер (с 2026-11-11): основной — сборка по дизайн-пакету с монтажными листами в edits/ (см. final_2026-11-09/ и .kimi-code/skills/kanal15-shorts/SKILL.md). Этот файл не брать в работу.

Вертикальный ролик (Shorts / Reels / TikTok) из записи поездки по описанию в JSON.
  python make_short.py shorts/01_kto_v_efire.json
Описание: {"src": "...mp4", "start": сек, "end": сек, "out": "имя.mp4", "hook": "крючок",
           "subs": [{"t": сек_от_начала_записи, "d": длительность, "who": "petrovna"|"player"|..., "text": "..."}]}
Кадр 1080x1920: квадрат из центра кабины посередине, сверху/снизу размытый фон; крючок сверху 3 с,
субтитры снизу (имя цветом), в конце 1.5 с заставка «КАНАЛ 15». Звук — как в записи (игра + рация + голос)."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTRO_S = 1.5
GOLD = "&H004EC1F2&"          # ASS colours are &HAABBGGRR
WHITE = "&H00FFFFFF&"
COLORS = {                    # speaker name colours (ASS BGR)
    "player": "&H004EC1F2&", "petrovna": "&H009C8CFF&", "mihalych": "&H0060B0FF&", "lastochka": "&H00E08CF0&",
    "vitek": "&H0070E070&", "ten": "&H00C0C0C0&", "stas": "&H00FFC060&", "yanek": "&H0080FFFF&",
    "boroda": "&H004080E0&", "bahti": "&H00FFB040&", "vera": "&H0080E0A0&", "rustam": "&H0040A0FF&", "buh": "&H00B0FFB0&", "foreign": "&H00D0D0D0&",
    "lisa": "&H003C8CFF&", "sova": "&H00E0C8A0&", "kardan": "&H006060FF&", "author": "&H00C0C0C0&",
}
NAMES = {"player": "Железяка", "petrovna": "Петровна", "mihalych": "Михалыч", "lastochka": "Ласточка",
         "vitek": "Витёк", "ten": "Тень", "stas": "Стас", "yanek": "Янек", "boroda": "Борода",
         "buh": "Бухгалтерия", "foreign": "Иностранец", "kardan": "Кардан", "lisa": "Лиса", "sova": "Сова",
         "palych": "Палыч", "student": "Студент", "professor": "Профессор", "rustam": "Самарканд",
         "bahti": "Ковбой", "vera": "Кинолог"}


def ts(s):
    s = max(0.0, s)
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def parts(spec):
    return [tuple(map(float, x)) for x in spec.get("parts") or [(spec["start"], spec["end"])]]


def out_time(spec, t):
    """Time in the recording -> time in the short (pieces glued together); None if it was cut out."""
    acc = 0.0
    for a, b in parts(spec):
        if a - 0.3 <= t < b:
            return acc + max(0.0, t - a)
        acc += b - a
    return None


def ass(spec, dur):
    F = spec.get("font", "Golos Text")   # user picked font 2 (2026-11-05)
    # stream layout: subtitles sit between the game (top) and the camera (bottom)
    sub_top = spec.get("sub_top", 1010 if spec.get("layout") == "stream" else 1550)
    name_mv = spec.get("name_mv", 1920 - sub_top + 8 if spec.get("layout") == "stream" else 330)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,{F},74,{WHITE},{WHITE},&H00000000&,&H80000000&,1,0,0,0,100,100,0,0,1,6,2,8,70,70,150,1
Style: Badge,{F},40,{GOLD},{GOLD},&H00000000&,&H00000000&,1,0,0,0,100,100,2,0,1,4,0,8,40,40,70,1
Style: Name,{F},56,{WHITE},{WHITE},&H00000000&,&H00000000&,1,0,0,0,100,100,0,0,1,5,0,2,60,60,{name_mv},1
Style: Sub,{F},68,{WHITE},{WHITE},&H00000000&,&H00000000&,1,0,0,0,100,100,0,0,1,6,1,8,70,70,{sub_top},1
Style: Outro,{F},110,{GOLD},{GOLD},&H00000000&,&H00000000&,1,0,0,0,100,100,4,0,1,7,0,5,40,40,0,1
Style: OutroSub,{F},52,{WHITE},{WHITE},&H00000000&,&H00000000&,1,0,0,0,100,100,0,0,1,5,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    body_end = dur - OUTRO_S
    hook_end = min(3.2, body_end)
    if spec.get("hook"):
        ev.append(f"Dialogue: 1,{ts(0)},{ts(hook_end)},Hook,,0,0,0,,{{\\fad(150,250)}}{spec['hook']}")
    ev.append(f"Dialogue: 0,{ts(hook_end)},{ts(body_end)},Badge,,0,0,0,,КАНАЛ 15")
    for s in spec.get("subs", []):
        a = out_time(spec, s["t"])
        if a is None:
            continue
        b = min(a + s["d"], body_end)
        if b <= 0 or a >= body_end:
            continue
        who = s.get("who", "")
        name = s.get("name") or NAMES.get(who, who)
        col = COLORS.get(who, WHITE)
        if name:
            ev.append(f"Dialogue: 2,{ts(a)},{ts(b)},Name,,0,0,0,,{{\\c{col}}}{name}")
        ev.append(f"Dialogue: 2,{ts(a)},{ts(b)},Sub,,0,0,0,,{s['text']}")
    ev.append(f"Dialogue: 3,{ts(body_end)},{ts(dur)},Outro,,0,0,0,,{{\\fad(200,0)\\pos(540,880)}}КАНАЛ 15")
    ev.append(f"Dialogue: 3,{ts(body_end)},{ts(dur)},OutroSub,,0,0,0,,{{\\fad(300,0)\\pos(540,1040)}}мультиплеер для интровертов")
    ev.append(f"Dialogue: 3,{ts(body_end + 0.2)},{ts(dur)},OutroSub,,0,0,0,,{{\\fad(300,0)\\pos(540,1120)\\fs40\\c&H00C0C0C0&}}рация для одиночной игры в ETS2")
    return head + "\n".join(ev) + "\n"


def main(spec_path):
    spec_path = Path(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    src = (spec_path.parent / spec["src"]).resolve() if not Path(spec["src"]).is_absolute() else Path(spec["src"])
    ps = parts(spec)
    body = sum(b - a for a, b in ps)
    s0 = ps[0][0]
    dur = body + OUTRO_S
    work = HERE / "work"
    work.mkdir(exist_ok=True)
    sub = work / (spec_path.stem + ".ass")
    sub.write_text(ass(spec, dur), encoding="utf-8")
    out = HERE / "out" / spec.get("out", spec_path.stem + ".mp4")
    out.parent.mkdir(exist_ok=True)
    # 2026-11-05: "layout": "phone" — a vertical phone video (the player at the wheel), full frame 1080x1920;
    # "bleep": [[t, d], ...] (recording time) — swear words muted under a 1 kHz tone
    phone = spec.get("layout") == "phone"
    stream = spec.get("layout") == "stream"
    W, H = 1964, 822           # source frame; square from the centre of the cab
    sq = H
    x0 = spec.get("crop_x", (W - sq) // 2)
    y0 = 0
    if spec.get("layout") == "game":   # 2026-11-06: a «Канал 15» stream VOD without the streamer: the game picture only
        W, H, sq, y0 = 1920, 804, 804, spec.get("game_y", 150)
        x0 = spec.get("crop_x", (W - sq) // 2)
    if spec.get("layout") == "rec":    # 2026-11-07: OBS profile «Канал 15 — Шортсы»: clean game 2580x1080, square 1:1
        W, H, sq, y0 = 2580, 1080, 1080, 0
        x0 = spec.get("crop_x", (W - sq) // 2)
    sub_f = str(sub).replace("\\", "/").replace(":", "\\:")
    cut = "".join(f"[0:v]trim={a - s0:.3f}:{b - s0:.3f},setpts=PTS-STARTPTS[v{i}];"
                  f"[0:a]atrim={a - s0:.3f}:{b - s0:.3f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:d=0.04,afade=t=out:st={b - a - 0.06:.3f}:d=0.06[a{i}];" for i, (a, b) in enumerate(ps))
    cut += "".join(f"[v{i}][a{i}]" for i in range(len(ps))) + f"concat=n={len(ps)}:v=1:a=1[cv][ca];"
    # 2026-11-06: "layout": "stream" — a Twitch VOD of «Канал 15» (1920x1080, game 21:9 at y=150, camera in its
    # ragged frame on the left): game centre on top, subtitles under it, the streamer's camera below
    gy = spec.get("game_y", 150)
    geq = f",eq={spec['eq']}" if spec.get("eq") else ""   # 2026-11-08: «eq»: "brightness=0.12" — lift night VOD game picture
    cx, cy, cw, ch = spec.get("cam", [20, 376, 318, 428])
    cam_w = round(cw * 1.55 / 2) * 2
    cam_h = round(ch * 1.55 / 2) * 2
    frame = (f"[cv]split=3[a][b][c];"
             f"[a]scale=-2:1920,crop=1080:1920,boxblur=30:3,eq=brightness=-0.25[bg];"
             f"[b]crop=1080:804:{spec.get('game_x', 420)}:{gy}{geq}[g];"
             f"[c]crop={cw}:{ch}:{cx}:{cy},scale={cam_w}:{cam_h}[cam];"
             f"[bg][g]overlay=0:170[t];[t][cam]overlay={(1080 - cam_w) // 2}:1225,fps=30," if stream else
             "[cv]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30," if phone else
             f"[cv]split=2[a][b];"
             f"[a]crop={W - 120}:{H - 40}:60:{20 + y0},scale=-2:1920,crop=1080:1920,boxblur=30:3,eq=brightness=-0.18[bg];"
             f"[b]crop={sq}:{sq}:{x0}:{y0},scale=1080:1080[fg];"
             f"[bg][fg]overlay=0:420,fps=30,")
    vf = (cut + frame +
          f"tpad=stop_mode=clone:stop_duration={OUTRO_S},"
          f"drawbox=enable='gte(t,{body:.2f})':x=0:y=0:w=iw:h=ih:color=black@0.82:t=fill,"
          f"ass='{sub_f}':fontsdir='C\\:/Windows/Fonts'[v]")
    af = f"[ca]afade=t=in:d=0.3,apad=pad_dur={OUTRO_S},afade=t=out:st={body - 0.2:.2f}:d={OUTRO_S + 0.2:.2f}[au]"
    bl = [(out_time(spec, t), d) for t, d in spec.get("bleep", [])]
    bl = [(a, d) for a, d in bl if a is not None]
    if bl:
        on = "+".join(f"between(t,{a:.2f},{a + d:.2f})" for a, d in bl)
        af = (f"[ca]volume=eval=frame:volume='1-({on})'[cm];"
              f"sine=f=1000:sample_rate=48000:d={body:.2f},volume=eval=frame:volume='0.22*({on})'[bp];"
              f"[cm][bp]amix=inputs=2:duration=first:normalize=0," + af[4:])
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{s0:.2f}", "-t", f"{ps[-1][1] - s0 + 0.5:.2f}", "-i", str(src),
           "-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[au]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    print("ГОТОВО:", out, f"{dur:.1f} с")


if __name__ == "__main__":
    main(sys.argv[1])
