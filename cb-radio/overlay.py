"""Оверлей рации для стрима (2026-11-06): рация отдаёт на этом компьютере страничку для OBS (источник «Браузер»).
    http://127.0.0.1:47823/            — оверлей 1920x1080: сверху «КАНАЛ 15» и кто в зоне, снизу субтитры
    http://127.0.0.1:47823/setup       — настройка оверлея: что и где показывать, готовый URL для OBS
Кадр стрима 16:9: игра 21:9 по центру (1920x804), полосы 138 px сверху и снизу — это и есть оверлей.
URL-параметры оверлея (решение 16.11, для чужих стримеров): brand/zone/subs/phone/top/bottom/bg = 0
прячут блоки, layout=classic|bottom|minimal, scale=0.5..2, accent=rrggbb — цвет акцента. Без параметров —
прежний вид. Всё настраивается на /setup без правки файлов.
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
# 22.11 (разбор стрима #13): lines 3 -> 50 (журнал в трее был мелким и без истории);
# history — полный журнал сессии для страницы /journal (включая sys-события)
STATE = {"inside": [], "lines": deque(maxlen=50), "history": deque(maxlen=500),
         "phone": 0.0, "seq": 0, "status": ""}
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
        if ln.get("ru"):                         # a foreigner's line: the subtitle is its Russian translation
            return ln["ru"]
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


JOURNAL = [None]   # 2026-11-07: folder for the subtitle journal (subs/<date>.jsonl) - only the user's own radio


def _push(who, text, kind, key=None, dur=None, t=None, journal=True, pending=False):
    """Одна строка в lines и history (ОДИН dict — правка по id обновляет обе очереди сразу).
    journal=False — pending-строка «Ты: …»: в subs/*.jsonl пишется только финальный текст (you_done)."""
    now = time.time()
    with _lock:
        STATE["seq"] += 1
        line = {"who": who, "text": text, "kind": kind, "t": now, "id": STATE["seq"], "pending": pending}
        STATE["lines"].append(line)
        STATE["history"].append(line)
    if journal and JOURNAL[0]:
        # every line on air with its wall-clock time: promo/shorts/draft_clips.py turns an OBS clip into a
        # finished subtitle spec (who said what and when) without speech recognition
        try:
            rec = {"t": round(t or now, 2), "who": key or "", "name": who, "text": text, "kind": kind}
            if dur:
                rec["d"] = round(dur, 2)
            with (JOURNAL[0] / f"{time.strftime('%Y-%m-%d')}.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass
    return line


def said(rel, actor, dur=None):
    """A radio line started playing. rel = path under audio/ without extension (variants/<v>/ prefix allowed)."""
    if not rel:
        return
    rel = re.sub(r"^variants/[^/]+/", "", rel)
    text = clean(_TEXT.get(rel, ""))
    if "/buh/" in rel or rel.startswith("reactions/buh"):
        with _lock:
            STATE["phone"] = time.time()
        _push("Бухгалтерия", text, "phone", "buh", dur)
        return
    if text and (actor or "").startswith("x_"):   # passing foreigner: «Проезжий», the text is the translation
        _push("Проезжий", text, "foreign", "foreign", dur)
    elif text:
        _push(_NAMES.get(actor, actor or "Эфир").split(" (")[0], text, "radio", actor, dur)


def foreign(lang_name):
    _push("Проезжий", f"говорит {lang_name}", "foreign", "foreign")


def you(text, t_end=None):
    """The player's words; t_end = wall-clock time he released the PTT (recognition comes a bit later)."""
    if text:
        _push("Ты", text, "you", "player", None, t_end)


def you_pending(t_end=None):
    """22.11 (стрим #13): нажатие тангенты ВИДНО СРАЗУ при отпускании, до распознавания — приглушённая
    строка «Ты: …» (kind 'you' + pending). Возвращает id; you_done() заменяет её текст на месте."""
    return _push("Ты", "…", "you", "player", None, t_end, journal=False, pending=True)["id"]


def you_done(lid, text, t_end=None):
    """22.11: распознавание вернулось (или таймаут) — та же строка заменяется на месте, новую не плодим.
    Пустой text = таймаут whisper -> «(не расслышано)»."""
    text = text or "(не расслышано)"
    with _lock:
        for l in STATE["lines"]:
            if l["id"] == lid:
                l["text"], l["pending"] = text, False
                break
    if JOURNAL[0]:
        try:
            rec = {"t": round(t_end or time.time(), 2), "who": "player", "name": "Ты", "text": text, "kind": "you"}
            with (JOURNAL[0] / f"{time.strftime('%Y-%m-%d')}.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass


def sys(text):
    """22.11 (стрим #13): системные события (заметка, штраф, режим стрима) — в /journal, НЕ в эфир OBS."""
    if text:
        _push("Канал 15", text, "sys", "sys")


def inside(keys, chips=None):
    """Who is in radio range; chips = {key: "♥♥ 😄"} - friendship hearts + mood (bonds.py), shown after the name."""
    names = [{"n": _NAMES.get(k, k).split(" (")[0], "s": (chips or {}).get(k, "")} for k in sorted(keys)]
    with _lock:
        STATE["inside"] = names


def bond(text):
    """Friendship level changed: «Лиса: теперь вы приятели ♥♥» as a line on the bottom bar."""
    if text:
        _push("Канал 15", text, "bond", "bond")


def snapshot():
    with _lock:
        return {"inside": list(STATE["inside"]), "lines": list(STATE["lines"]), "phone": STATE["phone"],
                "now": time.time()}


def journal_snapshot():
    """22.11: полный журнал сессии для страницы /journal (air + you + sys)."""
    with _lock:
        return {"history": list(STATE["history"]), "now": time.time()}


PAGE = r"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Канал 15 — оверлей</title>
<style>
:root{--gold:#f2c14e;--bar:rgba(10,12,18,.93);--text:#f2f2f2;--muted:#9aa3b2;--you:#8fd3ff;
 --line:color-mix(in srgb,var(--gold) 35%,transparent);--chipbg:color-mix(in srgb,var(--gold) 14%,transparent);
 --chipbrd:color-mix(in srgb,var(--gold) 55%,transparent)}
html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:transparent;
 font-family:"Segoe UI","Montserrat",Arial,sans-serif;color:var(--text)}
.bar{position:absolute;left:0;width:1920px;height:138px;background:var(--bar);display:flex;align-items:center;box-sizing:border-box}
#top{top:0;padding:0 56px;justify-content:space-between;border-bottom:2px solid var(--line)}
#bottom{bottom:0;padding:14px 56px;flex-direction:column;justify-content:center;align-items:flex-start;border-top:2px solid var(--line)}
.logo{display:flex;align-items:baseline;gap:22px}
.logo b{font-family:"Segoe UI Black","Segoe UI",Arial;font-size:58px;color:var(--gold);letter-spacing:1px}
.logo span{font-size:26px;color:var(--muted)}
.zone{display:flex;align-items:center;gap:14px;font-size:26px;color:var(--muted)}
#bottom .zone{font-size:22px;margin-bottom:2px}
#bottom .chip{font-size:22px;padding:4px 14px}
.chip{background:var(--chipbg);border:1px solid var(--chipbrd);color:var(--text);
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
.line.pending{opacity:.4;font-style:italic}   /* 22.11: «Ты: …» до распознавания — приглушённо */
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
const OVCFG=/*OVCFG*/{};
let NOSUBS=false;
(function(){ /* настройки оверлея из URL (см. /setup): бренд, зона, субтитры, плашка, полосы, layout, масштаб, акцент, фон */
 const C=OVCFG,$=id=>document.getElementById(id);
 const top=$('top'),bottom=$('bottom'),zone=$('zone'),phone=$('phone'),logo=top.querySelector('.logo');
 const v=(el,on)=>{el.style.display=on?'':'none'};
 if(C.accent)document.documentElement.style.setProperty('--gold','#'+C.accent);
 if(C.bg===false)document.documentElement.style.setProperty('--bar','transparent');
 if(C.scale&&C.scale!==1)document.body.style.zoom=C.scale;
 const layout=C.layout||'classic';
 if(layout==='minimal'){           /* только субтитры, без полос и фона */
  v(top,false);bottom.style.background='transparent';bottom.style.border='none';
  v(logo,false);v(zone,false);v(phone,false);
 }else if(layout==='bottom'){      /* всё внизу: логотип, зона и субтитры в нижней полосе */
  v(top,false);
  bottom.insertAdjacentElement('afterbegin',zone);
  if(C.brand!==false){bottom.insertAdjacentElement('afterbegin',logo);logo.style.marginBottom='4px'}
  v(zone,C.zone!==false);v(phone,C.phone!==false);
  if(C.subs===false){NOSUBS=true;if(C.brand===false&&C.zone===false)v(bottom,false)}
 }else{                            /* classic — как раньше */
  v(top,C.top!==false);v(bottom,C.bottom!==false);
  v(logo,C.brand!==false);v(zone,C.zone!==false);v(phone,C.phone!==false);
  if(C.subs===false){NOSUBS=true;v(bottom,false)}
  if(C.brand===false&&C.zone===false)v(top,false);
 }
})();
let last=-1, lasttxt="", talker=null;
function esc(s){return s.replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
async function tick(){
 try{
  const s=await (await fetch('/state',{cache:'no-store'})).json();
  const lines=s.lines.filter(l=>l.kind!=='sys'&&s.now-l.t<45);   /* 22.11: sys — только в /journal, не в эфир */
  const cur=lines.length?lines[lines.length-1]:null;
  talker=(cur&&cur.kind==='radio'&&s.now-cur.t<8)?cur.who:null;
  const z=document.getElementById('zone');
  z.innerHTML=s.inside.length?'в зоне рации:'+s.inside.map(c=>'<span class="chip'+(c.n===talker?' talk':'')+'">'+esc(c.n)+(c.s?'<span class="s">'+esc(c.s)+'</span>':'')+'</span>').join('')
                            :'<span class="quiet">в зоне рации никого</span>';
  const id=cur?cur.id:-1, txt=cur?cur.text:'';
  if(id!==last||txt!==lasttxt){   /* 22.11: pending-строка меняет текст на месте — перерисовываем и тогда */
   last=id; lasttxt=txt;
   const b=document.getElementById('bottom');
   b.innerHTML=NOSUBS?'':(lines.length?lines.slice(-2).map((l,i,a)=>'<div class="line '+l.kind+(l.pending?' pending':'')+(i<a.length-1?' old':'')+'"><span class="who">'+esc(l.who)+':</span>'+esc(l.text)+'</div>').join('')
                           :'<div class="quiet">Эфир на 15-м канале. Слышно только тех, кто рядом.</div>');
  }
  document.getElementById('phone').classList.toggle('on',s.now-s.phone<9&&!NOSUBS);
 }catch(e){}
 setTimeout(tick,300);
}
tick();
</script></body></html>"""


# 2026-11-07: vertical stream (Aitum Vertical, 1080x1920): /v
#   0..170 top bar (logo + who is in range, chips wrap), 170..1250 game square, 1250..1500 subtitles (wrapped,
#   bigger), 1500..1920 left free for the camera. Same /state as the horizontal page.
PAGE_V = r"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Канал 15 — вертикальный оверлей</title>
<style>
:root{--gold:#f2c14e;--bar:rgba(10,12,18,.93);--text:#f2f2f2;--muted:#9aa3b2;--you:#8fd3ff}
html,body{margin:0;width:1080px;height:1920px;overflow:hidden;background:transparent;position:relative;
 font-family:"Segoe UI","Montserrat",Arial,sans-serif;color:var(--text)}
#top{position:absolute;left:0;top:0;width:1080px;height:170px;background:var(--bar);box-sizing:border-box;padding:14px 34px;
 border-bottom:2px solid rgba(242,193,78,.35);display:flex;flex-direction:column;justify-content:center;gap:10px}
.logo{display:flex;align-items:baseline;gap:18px}
.logo b{font-family:"Segoe UI Black","Segoe UI",Arial;font-size:50px;color:var(--gold);letter-spacing:1px}
.logo span{font-size:24px;color:var(--muted)}
.zone{display:flex;flex-wrap:wrap;align-items:center;gap:8px 10px;font-size:22px;color:var(--muted);max-height:76px;overflow:hidden}
.chip{background:rgba(242,193,78,.14);border:1px solid rgba(242,193,78,.55);color:var(--text);padding:3px 12px;border-radius:18px;
 font-size:22px;white-space:nowrap}
.chip.talk{background:var(--gold);color:#111;font-weight:700}
.chip .s{margin-left:6px;font-size:19px}
#subs{position:absolute;left:0;top:1250px;width:1080px;height:250px;background:var(--bar);box-sizing:border-box;padding:16px 34px;
 border-top:2px solid rgba(242,193,78,.35);border-bottom:2px solid rgba(242,193,78,.35);display:flex;flex-direction:column;justify-content:center;gap:8px}
.line{font-size:38px;line-height:1.22;transition:opacity .6s;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.line .who{color:var(--gold);font-weight:700;margin-right:10px}
.line.you .who{color:var(--you)} .line.phone .who{color:#7ee08a} .line.bond .who{color:#ff8fb1} .line.bond{color:#ffd1dc}
.line.foreign .who{color:#c8c8c8}
.line.old{opacity:.45;font-size:28px;-webkit-line-clamp:1}
.line.pending{opacity:.4;font-style:italic}   /* 22.11: «Ты: …» до распознавания — приглушённо */
.quiet{font-size:28px;color:var(--muted)}
#phone{position:absolute;right:34px;top:1180px;background:var(--bar);border:2px solid #7ee08a;border-radius:16px;padding:10px 20px;
 font-size:26px;display:none;align-items:center;gap:10px}
#phone.on{display:flex;animation:ring .5s ease-in-out 4}
@keyframes ring{0%,100%{transform:rotate(0)}25%{transform:rotate(-3deg)}75%{transform:rotate(3deg)}}
</style></head><body>
<div id="top"><div class="logo"><b>КАНАЛ 15</b><span>мультиплеер для интровертов</span></div><div class="zone" id="zone"></div></div>
<div id="phone">📱 <span>Бухгалтерия — голосовое</span></div>
<div id="subs"><div class="quiet">Эфир на 15-м канале. Слышно только тех, кто рядом.</div></div>
<script>
let last=-1, lasttxt="", talker=null;
function esc(s){return s.replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
async function tick(){
 try{
  const s=await (await fetch('/state',{cache:'no-store'})).json();
  const lines=s.lines.filter(l=>l.kind!=='sys'&&s.now-l.t<45);   /* 22.11: sys — только в /journal, не в эфир */
  const cur=lines.length?lines[lines.length-1]:null;
  talker=(cur&&cur.kind==='radio'&&s.now-cur.t<8)?cur.who:null;
  document.getElementById('zone').innerHTML=s.inside.length?s.inside.map(c=>'<span class="chip'+(c.n===talker?' talk':'')+'">'+esc(c.n)+(c.s?'<span class="s">'+esc(c.s)+'</span>':'')+'</span>').join('')
                            :'<span class="quiet">в зоне рации никого</span>';
  const id=cur?cur.id:-1, txt=cur?cur.text:'';
  if(id!==last||txt!==lasttxt){
   last=id; lasttxt=txt;
   document.getElementById('subs').innerHTML=lines.length?lines.slice(-2).map((l,i,a)=>'<div class="line '+l.kind+(l.pending?' pending':'')+(i<a.length-1?' old':'')+'"><span class="who">'+esc(l.who)+':</span>'+esc(l.text)+'</div>').join('')
                           :'<div class="quiet">Эфир на 15-м канале. Слышно только тех, кто рядом.</div>';
  }
  document.getElementById('phone').classList.toggle('on',s.now-s.phone<9);
 }catch(e){}
 setTimeout(tick,300);
}
tick();
</script></body></html>"""


# Страница /journal (22.11, стрим #13): полный журнал сессии — эфир + «Ты: …» + системные события.
# Открывается из трея («Журнал эфира (веб)…»); автообновление 500 мс, автоскролл вниз.
PAGE_JOURNAL = r"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Канал 15 — журнал эфира</title>
<style>
:root{--gold:#f2c14e;--bar:rgba(10,12,18,.93);--text:#f2f2f2;--muted:#9aa3b2;--you:#8fd3ff}
html,body{margin:0;background:#0a0c12;color:var(--text);height:100%;
 font-family:"Segoe UI","Montserrat",Arial,sans-serif}
#wrap{max-width:1100px;margin:0 auto;padding:20px 28px 60px}
h1{font-size:26px;color:var(--gold);letter-spacing:1px;margin:14px 0 4px}
.sub{color:var(--muted);font-size:14px;margin-bottom:16px}
#log{display:flex;flex-direction:column;gap:6px;font-size:19px;line-height:1.4}
.row{display:flex;gap:14px;padding:7px 14px;border-radius:10px;background:rgba(255,255,255,.04)}
.row .tm{color:var(--muted);font-variant-numeric:tabular-nowrap;white-space:nowrap;font-size:16px;padding-top:2px}
.row .who{font-weight:700;color:var(--gold);white-space:nowrap}
.row.you .who{color:var(--you)}
.row.sys{background:transparent;border:1px dashed rgba(154,163,178,.35);color:var(--muted);font-size:16px}
.row.sys .who{color:var(--muted)}
.row.pending{opacity:.45;font-style:italic}
.empty{color:var(--muted);padding:20px 0}
</style></head><body>
<div id="wrap"><h1>КАНАЛ 15 — журнал эфира</h1>
<div class="sub">всё, что прозвучало в эфире, твои передачи и служебные события сессии</div>
<div id="log"><div class="empty">журнал пуст — пока тишина на 15-м канале</div></div></div>
<script>
let lastN=-1;
function esc(s){return s.replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
function tm(t){const d=new Date(t*1000);const p=n=>String(n).padStart(2,'0');
 return p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds())}
async function tick(){
 try{
  const s=await (await fetch('/journal_state',{cache:'no-store'})).json();
  const h=s.history;
  if(h.length!==lastN){          /* перерисовка только при изменении числа строк; скролл вниз — всегда */
   lastN=h.length;
   const el=document.getElementById('log');
   el.innerHTML=h.length?h.map(l=>'<div class="row '+l.kind+(l.pending?' pending':'')+'"><span class="tm">'+tm(l.t)+
    '</span><span class="who">'+esc(l.who)+':</span><span>'+esc(l.text)+'</span></div>').join('')
    :'<div class="empty">журнал пуст — пока тишина на 15-м канале</div>';
  }
  window.scrollTo(0,document.body.scrollHeight);
 }catch(e){}
 setTimeout(tick,500);
}
tick();
</script></body></html>"""


# Страница настройки /setup: чекбоксы, слайдер, цвет, живой предпросмотр и готовый URL для OBS.
# Предназначена для чужих стримеров: что показывать и как оформлять — решает стример, наша эмблема отключается.
PAGE_SETUP = r"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Канал 15 — настройка оверлея</title>
<style>
body{font-family:"Segoe UI",Arial,sans-serif;background:#14181f;color:#eee;max-width:1060px;margin:0 auto;padding:24px}
h1{font-size:1.4rem} h2{font-size:1.05rem;margin:22px 0 8px;color:#f2c14e}
label{display:inline-flex;align-items:center;gap:7px;margin:4px 18px 4px 0;font-size:.95rem;cursor:pointer}
input[type=range]{vertical-align:middle;width:180px}
fieldset{border:1px solid #2c3442;border-radius:10px;margin:0 0 6px}
#view{width:960px;height:540px;border:1px solid #2c3442;border-radius:8px;background:#222;
 transform-origin:0 0}
#url{width:100%;box-sizing:border-box;background:#0d1015;color:#9fd48b;border:1px solid #2c3442;
 border-radius:8px;padding:10px;font-size:.9rem;margin:8px 0}
button{background:#f2c14e;border:0;border-radius:8px;padding:10px 22px;font-weight:700;cursor:pointer}
.note{color:#8b93a1;font-size:.85rem}
</style></head><body>
<h1>Настройка оверлея «Канал 15»</h1>
<p class="note">Отметьте, что показывать, — предпросмотр и адрес для OBS обновятся сами.
В OBS добавьте источник «Браузер» на 1920×1080 и вставьте готовый адрес.</p>
<h2>Что показывать</h2>
<fieldset id="blocks">
 <label><input type="checkbox" id="brand" checked> Логотип «КАНАЛ 15» и слоган</label>
 <label><input type="checkbox" id="zone" checked> Кто в зоне рации</label>
 <label><input type="checkbox" id="subs" checked> Субтитры эфира</label>
 <label><input type="checkbox" id="phone" checked> Плашка «Бухгалтерия»</label><br>
 <label><input type="checkbox" id="top" checked> Верхняя полоса (фон)</label>
 <label><input type="checkbox" id="bottom" checked> Нижняя полоса (фон)</label>
 <label><input type="checkbox" id="bg" checked> Тёмный фон полос</label>
</fieldset>
<h2>Расположение</h2>
<label><input type="radio" name="layout" value="classic" checked> Классика — сверху эмблема и зона, снизу субтитры</label>
<label><input type="radio" name="layout" value="bottom"> Всё внизу</label>
<label><input type="radio" name="layout" value="minimal"> Только субтитры без полос</label>
<h2>Оформление</h2>
<label>Масштаб <input type="range" id="scale" min="0.5" max="2" step="0.05" value="1"> <span id="scalev">1.00</span></label>
<label>Цвет акцента <input type="color" id="accent" value="#f2c14e"></label>
<h2>Предпросмотр</h2>
<iframe id="view" src="/"></iframe>
<h2>Адрес для OBS</h2>
<input id="url" readonly>
<button id="copy">Скопировать</button> <span id="copied" class="note"></span>
<script>
const $=id=>document.getElementById(id);
function params(){
 const p=new URLSearchParams();
 const layout=document.querySelector('input[name=layout]:checked').value;
 p.set('layout',layout);
 const off=['brand','zone','subs','phone','top','bottom','bg'];
 for(const k of off){
  const el=$(k),on=el.checked;
  el.parentElement.style.opacity=(layout!=='classic'&&(k==='top'||k==='bottom'))?.4:1;
  if((k==='top'||k==='bottom')&&layout!=='classic')continue;   /* полосы переключаются layout'ом */
  if(!on)p.set(k,'0');
 }
 const sc=parseFloat($('scale').value);
 $('scalev').textContent=sc.toFixed(2);
 if(sc!==1)p.set('scale',sc);
 const ac=$('accent').value.slice(1);
 if(ac!=='f2c14e')p.set('accent',ac);
 return p;
}
function refresh(){
 const q=params().toString(),url='http://127.0.0.1:47823/'+(q?'?'+q:'');
 $('view').src='/'+(q?'?'+q:'');
 $('url').value=url;
}
document.getElementById('blocks').addEventListener('change',refresh);
document.querySelectorAll('input[name=layout]').forEach(el=>el.addEventListener('change',refresh));
$('scale').addEventListener('input',refresh);
$('accent').addEventListener('input',refresh);
$('copy').addEventListener('click',async()=>{
 try{await navigator.clipboard.writeText($('url').value);$('copied').textContent='скопировано';}
 catch(e){$('url').select();document.execCommand('copy');$('copied').textContent='скопировано (старый способ)';}
 setTimeout(()=>$('copied').textContent='',2000);
});
refresh();
</script></body></html>"""


def _overlay_cfg(query):
    """URL-параметры оверлея -> JS-конфиг (см. /setup). Дефолт = прежний вид без параметров."""
    def flag(name, default=True):
        return query.get(name, [str(int(default))])[0] != "0"
    layout = query.get("layout", ["classic"])[0]
    if layout not in ("classic", "bottom", "minimal"):
        layout = "classic"
    try:
        scale = min(2.0, max(0.5, float(query.get("scale", ["1"])[0])))
    except ValueError:
        scale = 1.0
    accent = query.get("accent", [""])[0].lower()
    if not re.fullmatch(r"[0-9a-f]{6}", accent):
        accent = ""
    return {"brand": flag("brand"), "zone": flag("zone"), "subs": flag("subs"),
            "phone": flag("phone"), "top": flag("top"), "bottom": flag("bottom"),
            "layout": layout, "scale": scale, "accent": accent, "bg": flag("bg")}


class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import parse_qs, urlsplit
        u = urlsplit(self.path)
        if u.path == "/state":
            body, ctype = json.dumps(snapshot(), ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"
        elif u.path == "/journal_state":                       # 22.11: полный журнал сессии для /journal
            body, ctype = json.dumps(journal_snapshot(), ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"
        elif u.path == "/journal":                             # 22.11: страница журнала эфира (из трея)
            body, ctype = PAGE_JOURNAL.encode("utf-8"), "text/html; charset=utf-8"
        elif u.path.rstrip("/") == "/v":
            body, ctype = PAGE_V.encode("utf-8"), "text/html; charset=utf-8"
        elif u.path == "/setup":
            body, ctype = PAGE_SETUP.encode("utf-8"), "text/html; charset=utf-8"
        else:
            cfg = json.dumps(_overlay_cfg(parse_qs(u.query)), separators=(",", ":"))
            body, ctype = PAGE.replace("/*OVCFG*/", cfg).encode("utf-8"), "text/html; charset=utf-8"
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


def start(port, phrases_json, build="", log=print, journal=None):
    if journal:
        try:
            Path(journal).mkdir(parents=True, exist_ok=True)
            JOURNAL[0] = Path(journal)
        except Exception:
            JOURNAL[0] = None
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
