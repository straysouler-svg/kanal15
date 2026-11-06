"""Оверлей рации для стрима (2026-11-06): рация отдаёт на этом компьютере страничку для OBS (источник «Браузер»).
    http://127.0.0.1:47823/            — оверлей 1920x1080: сверху «КАНАЛ 15» и кто в зоне, снизу субтитры
Кадр стрима 16:9: игра 21:9 по центру (1920x804), полосы 138 px сверху и снизу — это и есть оверлей.
Слушает только 127.0.0.1 (из сети недоступен). Ничего не открывает и не трогает фокус игры.
Текст реплики берётся по звуковому файлу из phrases/level3_eleven.json; в личных и общей сборках —
вариант с нужным обращением (v_kirill / v_alive / v_neutral), никогда не «Железяка» чужому игроку."""
import json
import re
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_lock = threading.Lock()
STATE = {"inside": [], "lines": deque(maxlen=3), "phone": 0.0, "seq": 0, "status": ""}
_TEXT, _NAMES = {}, {}
_TAGS = re.compile(r"\[[^\]]*\]\s*|\([^)]*\)\s*")


def clean(t):
    return re.sub(r"\s{2,}", " ", _TAGS.sub("", t or "")).strip()


def load_texts(phrases_json, build=""):
    """rel path ("reactions/player/greet/05", "level3/mihalych/03", "scenes/x/02") -> display text."""
    d = json.loads(Path(phrases_json).read_text(encoding="utf-8"))
    key = f"v_{build}" if build else None

    def txt(ln):
        if isinstance(ln, str):
            return ln
        if key and key in ln:
            return ln[key]
        if build and "v_neutral" in ln and key not in ln:
            return ln["v_neutral"]               # a build without its own version: never the user's «Железяка»
        return ln.get("text", "")
    for k, a in d.get("actors", {}).items():
        _NAMES[k] = a.get("name", k)
        for i, ph in enumerate(a.get("phrases", []), 1):
            _TEXT[f"level3/{k}/{i:02d}"] = txt(ph)
    for sid, ls in d.get("scenes", {}).items():
        for i, ln in enumerate(ls, 1):
            _TEXT[f"scenes/{sid}/{i:02d}"] = txt(ln)
    for g, ks in d.get("reactions", {}).items():
        if g.startswith("_"):
            continue
        for k, ls in ks.items():
            if k.startswith("_"):
                continue
            for i, ln in enumerate(ls, 1):
                _TEXT[f"reactions/{g}/{k}/{i:02d}"] = txt(ln)


def add_texts(m):
    """Extra rel -> text (secret lines of a build, tainik.py)."""
    _TEXT.update(m or {})


def _push(who, text, kind):
    with _lock:
        STATE["seq"] += 1
        STATE["lines"].append({"who": who, "text": text, "kind": kind, "t": time.time(), "id": STATE["seq"]})


def said(rel, actor):
    """A radio line started playing. rel = path under audio/ without extension (variants/<v>/ prefix allowed)."""
    if not rel:
        return
    rel = re.sub(r"^variants/[^/]+/", "", rel)
    text = clean(_TEXT.get(rel, ""))
    if "/buh/" in rel or rel.startswith("reactions/buh"):
        with _lock:
            STATE["phone"] = time.time()
        _push("Бухгалтерия", text, "phone")
        return
    if text:
        _push(_NAMES.get(actor, actor or "Эфир").split(" (")[0], text, "radio")


def foreign(lang_name):
    _push("Проезжий", f"говорит {lang_name}", "foreign")


def you(text):
    if text:
        _push("Ты", text, "you")


def inside(keys, chips=None):
    """Who is in radio range; chips = {key: "♥♥ 😄"} - friendship hearts + mood (bonds.py), shown after the name."""
    names = [{"n": _NAMES.get(k, k).split(" (")[0], "s": (chips or {}).get(k, "")} for k in sorted(keys)]
    with _lock:
        STATE["inside"] = names


def bond(text):
    """Friendship level changed: «Лиса: теперь вы приятели ♥♥» as a line on the bottom bar."""
    if text:
        _push("Канал 15", text, "bond")


def snapshot():
    with _lock:
        return {"inside": list(STATE["inside"]), "lines": list(STATE["lines"]), "phone": STATE["phone"],
                "now": time.time()}


PAGE = r"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Канал 15 — оверлей</title>
<style>
:root{--gold:#f2c14e;--bar:rgba(10,12,18,.93);--text:#f2f2f2;--muted:#9aa3b2;--you:#8fd3ff}
html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:transparent;
 font-family:"Segoe UI","Montserrat",Arial,sans-serif;color:var(--text)}
.bar{position:absolute;left:0;width:1920px;height:138px;background:var(--bar);display:flex;align-items:center;box-sizing:border-box}
#top{top:0;padding:0 56px;justify-content:space-between;border-bottom:2px solid rgba(242,193,78,.35)}
#bottom{bottom:0;padding:14px 56px;flex-direction:column;justify-content:center;align-items:flex-start;border-top:2px solid rgba(242,193,78,.35)}
.logo{display:flex;align-items:baseline;gap:22px}
.logo b{font-family:"Segoe UI Black","Segoe UI",Arial;font-size:58px;color:var(--gold);letter-spacing:1px}
.logo span{font-size:26px;color:var(--muted)}
.zone{display:flex;align-items:center;gap:14px;font-size:26px;color:var(--muted)}
.chip{background:rgba(242,193,78,.14);border:1px solid rgba(242,193,78,.55);color:var(--text);
 padding:6px 16px;border-radius:22px;font-size:26px;white-space:nowrap}
.chip.talk{background:var(--gold);color:#111;font-weight:700}
.line{font-size:30px;line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:1808px;
 transition:opacity .6s}
.line .who{color:var(--gold);font-weight:700;margin-right:12px}
.line.you .who{color:var(--you)}
.line.phone .who{color:#7ee08a}
.line.bond .who{color:#ff8fb1}
.line.bond{color:#ffd1dc}
.chip .s{margin-left:8px;font-size:22px;opacity:.9}
.line.old{opacity:.45;font-size:26px}
#phone{position:absolute;right:56px;bottom:160px;background:var(--bar);border:2px solid #7ee08a;border-radius:18px;
 padding:16px 26px;font-size:28px;display:none;align-items:center;gap:14px}
#phone.on{display:flex;animation:ring .5s ease-in-out 4}
@keyframes ring{0%,100%{transform:rotate(0)}25%{transform:rotate(-3deg)}75%{transform:rotate(3deg)}}
.quiet{font-size:26px;color:var(--muted)}
</style></head><body>
<div id="top" class="bar"><div class="logo"><b>КАНАЛ 15</b><span>мультиплеер для интровертов</span></div>
<div class="zone" id="zone"></div></div>
<div id="phone">📱 <span>Бухгалтерия — голосовое сообщение</span></div>
<div id="bottom" class="bar"><div class="quiet">Эфир на 15-м канале. Слышно только тех, кто рядом.</div></div>
<script>
let last=-1, talker=null;
function esc(s){return s.replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
async function tick(){
 try{
  const s=await (await fetch('/state',{cache:'no-store'})).json();
  const lines=s.lines.filter(l=>s.now-l.t<45);
  const cur=lines.length?lines[lines.length-1]:null;
  talker=(cur&&cur.kind==='radio'&&s.now-cur.t<8)?cur.who:null;
  const z=document.getElementById('zone');
  z.innerHTML=s.inside.length?'в зоне рации:'+s.inside.map(c=>'<span class="chip'+(c.n===talker?' talk':'')+'">'+esc(c.n)+(c.s?'<span class="s">'+esc(c.s)+'</span>':'')+'</span>').join('')
                            :'<span class="quiet">в зоне рации никого</span>';
  const id=cur?cur.id:-1;
  if(id!==last){
   last=id;
   const b=document.getElementById('bottom');
   b.innerHTML=lines.length?lines.slice(-2).map((l,i,a)=>'<div class="line '+l.kind+(i<a.length-1?' old':'')+'"><span class="who">'+esc(l.who)+':</span>'+esc(l.text)+'</div>').join('')
                           :'<div class="quiet">Эфир на 15-м канале. Слышно только тех, кто рядом.</div>';
  }
  document.getElementById('phone').classList.toggle('on',s.now-s.phone<9);
 }catch(e){}
 setTimeout(tick,300);
}
tick();
</script></body></html>"""


class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/state"):
            body, ctype = json.dumps(snapshot(), ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"
        else:
            body, ctype = PAGE.encode("utf-8"), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


_SRV = [None]


def stop():
    srv, _SRV[0] = _SRV[0], None
    if srv:
        try:
            srv.shutdown()
            srv.server_close()
        except Exception:
            pass


def start(port, phrases_json, build="", log=print):
    if _SRV[0]:
        return _SRV[0]
    try:
        load_texts(phrases_json, build)
        srv = ThreadingHTTPServer(("127.0.0.1", int(port)), _H)
    except Exception as e:
        log(f"оверлей для стрима не запустился: {e!r}")
        return None
    _SRV[0] = srv
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"оверлей для стрима: http://127.0.0.1:{port}/ (OBS → источник «Браузер», 1920x1080)")
    return srv
