"""Собирает из черновика поста (md) страницу-предпросмотр и картинку-длиннопост.
Запуск:  python build_longpost.py ../pikabu_post_b_v2_2026-11-11.md pikabu_v2 "Пикабу"
Результат: preview_<имя>.html и <имя>_longpost.png рядом со скриптом."""
import html, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = """
  body { margin:0; background:#111B18; color:#F1E9D7; font-family: Georgia, 'Times New Roman', serif; }
  .col { max-width:760px; margin:0 auto; padding:40px 26px 70px; }
  h1 { font-size:35px; line-height:1.32; color:#FFF9ED; margin:24px 0 10px; }
  .meta { color:#A8B69D; font-size:16px; margin-bottom:24px; }
  img { width:100%; border-radius:8px; display:block; }
  img.cover { border-radius:12px; margin:22px 0; box-shadow:0 8px 40px rgba(0,0,0,.55); }
  img.banner { margin:32px 0; box-shadow:0 4px 24px rgba(0,0,0,.5); }
  p { font-size:21px; line-height:1.66; margin:18px 0; }
  p.sec { color:#D69A45; font-weight:bold; margin-top:36px; font-size:24px;
          border-bottom:1px dashed #4a5a44; padding-bottom:6px; }
  p.sec.caps { letter-spacing:.14em; font-size:21px; }
  ul { padding-left:26px; margin:10px 0; } li { font-size:21px; line-height:1.6; margin:14px 0; }
  ul.log { list-style:none; padding-left:0; }
  ul.log li { border-left:3px solid #D69A45; padding-left:16px; margin:20px 0; }
  a { color:#D69A45; word-break:break-all; }
  .links { border-top:1px solid #223F2F; margin-top:34px; padding-top:20px; }
  .links p { font-size:19px; margin:8px 0; }
"""


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', s)


def build(md_path, name, site):
    text = Path(md_path).read_text(encoding="utf-8")
    title = re.search(r"\*\*Заголовок:\*\*\s*(.+)", text).group(1).strip()
    body = text.split("\n---\n")[2]                  # шапка --- заголовки --- ТЕЛО --- примечания
    out, items, kind = [], [], None

    def flush():
        nonlocal items, kind
        if items:
            cls = ' class="log"' if kind == "log" else ""
            out.append(f"<ul{cls}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
        items, kind = [], None

    first_img = True
    for raw in body.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"\*\[картинка:\s*([\w.]+)", line)
        if m:
            flush()
            out.append(f'<img class="{"cover" if first_img else "banner"}" src="{m.group(1)}" alt="">')
            first_img = False
        elif re.fullmatch(r"\*\*[^*]+\*\*", line):
            flush()
            t = line.strip("*")
            out.append(f'<p class="sec{" caps" if t.isupper() else ""}">{inline(t)}</p>')
        elif line.startswith("- ") or line.startswith("— "):
            k = "log" if line.startswith("—") else "dot"
            if kind and kind != k:
                flush()
            kind = k
            items.append(line[2:])
        elif line.startswith("http") or line.startswith("Кусок эфира") or line.startswith("Скачать"):
            flush()
            if not out or not out[-1].startswith('<div class="links">'):
                out.append('<div class="links">')
            out[-1] += f"<p>{inline(line)}</p>"
        else:
            flush()
            out.append(f"<p>{inline(line)}</p>")
    flush()
    out = [o + "</div>" if o.startswith('<div class="links">') else o for o in out]
    page = (f'<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>Канал 15 — {site}</title>'
            f"<style>{CSS}</style></head><body><div class=\"col\"><h1>{inline(title)}</h1>"
            + "\n".join(out) + "</div></body></html>")
    dst = HERE / f"preview_{name}.html"
    dst.write_text(page, encoding="utf-8")
    return dst


def shot(page, name, width=812, height=16000):
    """Снимок страницы безголовым Edge/Chrome, затем обрезка пустого низа."""
    from PIL import Image
    png = HERE / f"{name}_longpost.png"
    for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if Path(exe).exists():
            break
    else:
        return None
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={width},{height}",
                    "--force-device-scale-factor=1", f"--screenshot={png}", page.as_uri()],
                   check=True, capture_output=True, timeout=120)
    im = Image.open(png).convert("RGB")
    bg = im.getpixel((2, im.height - 2))
    px = im.load()
    y = im.height - 1
    while y > 0 and all(px[x, y] == bg for x in range(40, im.width - 40, 6)):
        y -= 1
    im.crop((0, 0, im.width, min(im.height, y + 60))).save(png, optimize=True)
    return png


if __name__ == "__main__":
    md, name, site = sys.argv[1], sys.argv[2], sys.argv[3]
    p = build(md, name, site)
    print(p.name, shot(p, name))
