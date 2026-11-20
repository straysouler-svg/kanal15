# -*- coding: utf-8 -*-
"""Метрики YouTube в режиме стримера (пилот 19.11, stream_viewers_pilot) + питч донатов
(stream_donate_pitch_pilot, 19.11, волна 2 по решению пользователя).

Опрос YouTube Data API, решение о событиях и состояние — здесь; cb_radio.py только зовёт
tick()/chat_tick()/subs_tick()/superchat_tick()/pitch_tick() и звучит голосовое бухгалтерии
из пулов buh/{viewers,donate_pitch/*,chat,subs,superchat} — цифры в реплики НЕ вшиваются.

Уроки ноября: таймеры — в НАСТОЯЩИХ секундах (единицы в именах, правило 1); состояние — в своём
файле viewers_state.json (v=2, терпимая миграция, правило 8); журнал отвечает «почему» (правило 7);
не долбим API: cb_radio зовёт опросы по их интервалам и только при включённом режиме стримера.

Токен — promo/youtube/token.json (см. promo/youtube/upload_short.py); google-либы есть только
на машине стримера: токена/либ нет — пилот тихо отключается (по умолчанию выключен anyway).

Квота YouTube (сумма на 1 час стрима, считал при вводе): viewers 12×1=12, chat 60×5=300,
subs 4×1=4, superchat 12×1=12 — итого ~328 ед./час из 10 000/сутки: стрим 8 ч = ~2 600 ед.,
остаток есть. Интервалы — константы ниже, менять только их.

Тесты без сети: fetch подменяется в тиках; моки — test_streampeek.py / test_pitch.py.
"""
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOKEN_F = HERE.parent / "promo" / "youtube" / "token.json"
STATE_F = HERE / "viewers_state.json"
YT_API = "https://www.googleapis.com/youtube/v3"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

POLL_EVERY_S = 300          # настоящие секунды: зрители, раз в 5 мин
CHAT_POLL_EVERY_S = 60      # настоящие секунды: чат; вызов = 5 единиц квоты (~300 ед./час)
CHAT_ACTIVE_N = 4           # столько сообщений за тик — «чат ожил»
CHAT_ACTIVE_COOL_S = 1200.0 # настоящие секунды: active — не чаще раза в 20 мин
CHAT_QUIET_AFTER_S = 1200.0 # настоящие секунды: тишина чата столько при зрителях >0 — повод quiet
CHAT_QUIET_COOL_S = 2400.0  # настоящие секунды: quiet — не чаще раза в 40 мин
SUBS_POLL_EVERY_S = 900     # настоящие секунды: подписчики, раз в 15 мин
SUBS_MIN_GAP_S = 1800.0     # настоящие секунды: прирост подписчиков — не чаще раза в 30 мин
SUPERCHAT_POLL_EVERY_S = 300  # настоящие секунды: Super Chat, раз в 5 мин
PITCH_GAP_MIN_S = 900.0     # настоящие секунды: общий заслон питча — не чаще раза в 15-18 мин
PITCH_GAP_JITTER_S = 180.0  # настоящие секунды: джиттер заслона (итого 15-18 мин, решение пользователя)
PITCH_KIND_WINDOW_S = 900.0 # настоящие секунды: донат за последние 15 мин глушит economy и
                            # viewers_no_donations — «не канючить на волне щедрости»
PITCH_NO_DON_AFTER_S = 1200.0  # настоящие секунды: зрителей ≥5 и донатов не было столько — повод
PITCH_NORM_EVERY_S = 2700.0 # настоящие секунды: нормативный питч — раз в ~45 мин
PITCH_AFTER_MIN_S = 60.0    # настоящие секунды: после доната — не раньше минуты
PITCH_AFTER_MAX_S = 120.0   # настоящие секунды: ...и не позже двух (окно after_donation)
PITCH_AFTER_P = 0.5         # шанс after_donation (бросок кэшируется на донат, не на каждый тик)
ZERO_COOL_S = 1800.0        # настоящие секунды: «0 зрителей» — не чаще раза в ~30 мин (monotonic)
RECORD_MIN_GAP_S = 300.0    # настоящие секунды: гистерезис рекорда — не чаще раза в 5 мин
RECORD_STEP = 3             # гистерезис рекорда: звучим, только если счётчик вырос на шаг от
                            # последней ОЗВУЧЕННОЙ планки (планка сама тихо ползёт за максимумом —
                            # «не звучать на каждое +1» при опросе раз в 5 мин)
BET_P = 0.35                # шанс разовой на сессию фишки «спор с Михалычем» после first/record
MOCK = os.environ.get("K15_YT_MOCK")   # тесты: json-ответ videos.list, без сети

_disabled = None            # причина тихого отключения (токена/либ нет) — log один раз


def log_default(msg):
    try:
        print(msg, flush=True)
    except Exception:
        pass


def load_state():
    """viewers_state.json v=2 — терпимая загрузка и миграция (правило 8): нет файла/полей v=1 —
    дефолты, не падение."""
    d = {"v": 2, "viewers": None, "record": 0, "record_ann": 0, "last_zero": 0.0,
         "last_record": 0.0, "bet_done": False, "bet_roll": None, "seed": None,
         # волна 2: чат
         "chat_id": None, "chat_first": False, "chat_active_ann": 0.0, "chat_quiet_since": 0.0,
         "chat_quiet_ann": 0.0,
         # подписчики
         "subs_start": None, "subs_ann": 0.0,
         # super chat
         "sc_seen": [], "sc_off": False,
         # питч донатов
         "donation_last": 0.0, "pitch_last": 0.0, "pitch_after_done": False,
         "after_roll": None, "pitch_economy_next": 0.0, "pitch_norm_next": 0.0}
    try:
        st = json.loads(STATE_F.read_text(encoding="utf-8"))
        if isinstance(st, dict):
            d.update({k: st[k] for k in d if k in st})
    except (OSError, ValueError):
        pass
    return d


def save_state(st):
    try:
        STATE_F.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def session_start(st=None, now=None):
    """Новая сессия стрима (cb_radio зовёт на фронте включения режима): обнуляем сессионные
    поля, зерно — свежее (случайность с зерном, правило 8). Возвращает состояние.
    Временные метки — «сейчас» (monotonic), НЕ 0.0: иначе против monotonic() они дают
    «тишину в тысячах секунд» и питч на 1-й минуте (баги 20.11, симуляция stream_epoch)."""
    now = time.monotonic() if now is None else now
    st = st if st is not None else load_state()
    st.update({"viewers": None, "record": 0, "record_ann": 0, "last_zero": 0.0,
               "last_record": 0.0, "bet_done": False, "bet_roll": None,
               "chat_id": None, "chat_first": False, "chat_active_ann": 0.0,
               "chat_quiet_since": now, "chat_quiet_ann": 0.0,
               "subs_start": None, "subs_ann": 0.0, "sc_seen": [], "sc_off": False,
               "donation_last": 0.0, "pitch_last": now, "pitch_after_done": False,
               "after_roll": None, "pitch_economy_next": now + PITCH_GAP_MIN_S,
               "pitch_norm_next": 0.0,
               "seed": random.randrange(2 ** 31)})
    save_state(st)
    return st


def _token(log):
    """access token из promo/youtube/token.json; при истечении — refresh. Раньше refresh шёл через
    google-либы, и при ImportError пилот отключался НАВСЕГДА (стрим 20.11: в окружении рации
    coop-buddy venv либ нет). Теперь refresh — stdlib-only (OAuth refresh_token grant, те же
    client_id/secret из token.json) — зависимостей нет вообще. Отключение пилота — только при
    отсутствии/битом token.json (постоянное); сетевые ошибки — None и повтор на следующем тике."""
    global _disabled
    if _disabled:
        return None, _disabled
    if not TOKEN_F.exists():
        _disabled = "нет promo/youtube/token.json (только на машине стримера)"
        log(f"зрители: пилот выключен — {_disabled}")
        return None, _disabled
    try:
        stored = json.loads(TOKEN_F.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        _disabled = f"token.json не читается: {e!r}"
        log(f"зрители: пилот выключен — {_disabled}")
        return None, _disabled
    exp = stored.get("expiry")
    try:
        fresh = exp and datetime.fromisoformat(exp.replace("Z", "+00:00")) > \
            datetime.fromtimestamp(time.time() + 300, timezone.utc)
    except ValueError:
        fresh = False
    if fresh and stored.get("token"):
        return stored["token"], None
    rt = stored.get("refresh_token")
    if not rt or not stored.get("client_id"):
        _disabled = "в token.json нет refresh_token/client_id — переавторизуйся (upload_short.py)"
        log(f"зрители: пилот выключен — {_disabled}")
        return None, _disabled
    body = urllib.parse.urlencode({
        "client_id": stored["client_id"],
        "client_secret": stored.get("client_secret", ""),
        "refresh_token": rt,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tok = json.loads(r.read())
    except Exception as e:                  # сеть/401: НЕ отключаем пилот, следующий тик повторит
        log(f"зрители: refresh токена не удался: {e!r}")
        return None, "refresh failed"
    access = tok.get("access_token")
    if not access:
        log(f"зрители: в ответе refresh нет access_token: {sorted(tok)}")
        return None, "refresh failed"
    stored.update(token=access, expiry=datetime.fromtimestamp(
        time.time() + int(tok.get("expires_in", 3600)) - 300, timezone.utc).isoformat())
    try:
        TOKEN_F.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return access, None


_last_fail_log = 0.0                # throttle лога сетевых ошибок (не чаще раза в 10 мин)
FAIL_LOG_EVERY_S = 600.0


def _fail_log(log, msg):
    global _last_fail_log
    now = time.monotonic()
    if now - _last_fail_log >= FAIL_LOG_EVERY_S:
        _last_fail_log = now
        log(msg)


def _fetch(log):
    """-> int зрителей или None (нет активного эфира / сбой — пилот остаётся в строю, тик повторит).
    Мок K15_YT_MOCK — без сети (тесты). Два шага: liveBroadcasts.list(active) -> id эфира
    (= videoId), videos.list(id).liveStreamingDetails.concurrentViewers (стрим 20.11: videos.list
    с broadcastStatus отвечал 400 — этот параметр там не поддерживается)."""
    if MOCK:
        data = json.loads(Path(MOCK).read_text(encoding="utf-8"))
        items = data.get("items") or []
        if not items:
            return None
        try:
            return int(items[0].get("liveStreamingDetails", {}).get("concurrentViewers"))
        except (TypeError, ValueError):
            return None
    token, why = _token(log)
    if not token:
        return None

    def api(path, params):
        url = f"{YT_API}/{path}?" + urllib.parse.urlencode(dict(params, access_token=token))
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    try:
        br = api("liveBroadcasts", {"part": "id", "broadcastStatus": "active"})
        items = br.get("items") or []
        if not items:
            return None                      # активного эфира нет
        vid = items[0].get("id")
        if not vid:
            return None
        data = api("videos", {"part": "liveStreamingDetails", "id": vid})
    except Exception as e:
        _fail_log(log, f"зрители: опрос не удался: {e!r}")
        return None
    items = data.get("items") or []
    if not items:
        return None
    try:
        return int(items[0].get("liveStreamingDetails", {}).get("concurrentViewers"))
    except (TypeError, ValueError):
        return None


def decide(st, viewers, now, rnd, log):
    """Событие по смене счётчика -> категория пула (zero/first/record/bet) или None.
    Правит st; журнал отвечает «почему не звучим» (правило 7). now — monotonic, _S."""
    prev = st.get("viewers")
    st["viewers"] = viewers
    if viewers is None:
        return None
    ev = None
    if prev and prev > 0 and viewers == 0:
        if now - st.get("last_zero", 0.0) >= ZERO_COOL_S:
            ev, st["last_zero"] = "zero", now
            log(f"зрители: {prev} -> 0 — zero")
        else:
            log(f"зрители: 0, но реплика была {(now - st.get('last_zero', 0.0)) / 60:.0f} мин назад — молчим")
    elif (prev == 0 or prev is None) and viewers > 0:
        ev = "first"
        log(f"зрители: 0 -> {viewers} — first")
    if viewers > st.get("record", 0):
        st["record"] = viewers
    if viewers >= st.get("record_ann", 0) + RECORD_STEP:
        if ev == "first":
            st["record_ann"] = viewers
            log(f"зрители: озвученная планка {viewers} (first уже звучит)")
        elif now - st.get("last_record", 0.0) >= RECORD_MIN_GAP_S:
            st.update(record_ann=viewers, last_record=now)
            ev = ev or "record"
            log(f"зрители: новый максимум {viewers} — record")
        else:
            log(f"зрители: рекорд {viewers}, но планка звучала "
                f"{(now - st.get('last_record', 0.0)) / 60:.1f} мин назад — молчим")
    elif viewers == st.get("record"):
        log(f"зрители: максимум {viewers} растёт меньше чем на {RECORD_STEP} от озвученной "
            f"планки {st.get('record_ann', 0)} — молчим")
    if ev in ("first", "record") and not st.get("bet_done"):
        # фишка решается ОДИН раз за сессию: бросок кэшируется (bet_roll), а не тянется
        # на каждом first/record — иначе при ~5 событиях на стриме шанс 0.35 превращается в ~99%
        if st.get("bet_roll") is None:
            st["bet_roll"] = rnd.random()
        if st["bet_roll"] < BET_P:
            st["bet_done"] = True
            log(f"зрители: фишка «спор с Михалычем» вместо {ev}")
            return "bet"
    return ev


def tick(now=None, log=log_default, state_f=None, fetch=None):
    """Один опрос (cb_radio: раз в POLL_EVERY_S, только в режиме стримера) -> категория или None."""
    global STATE_F
    if state_f is not None:
        STATE_F = state_f
    now = time.monotonic() if now is None else now
    st = load_state()
    rnd = random.Random(st.get("seed"))       # зерно сессии (правило 8)
    viewers = (fetch or _fetch)(log)
    if viewers is None:
        save_state(st)
        return None
    ev = decide(st, viewers, now, rnd, log)
    save_state(st)
    return ev


def _api_get(endpoint, params, log, fetch=None):
    """Подписанный (токеном) GET к YouTube Data API -> dict. fetch подменяется в тестах.
    Сетевые ошибки — в лог, без падения (правило: не долбим API)."""
    if fetch is not None:
        return fetch(endpoint, params)
    token, why = _token(log)
    if not token:
        return None
    q = urllib.parse.urlencode(dict(params, access_token=token))
    req = urllib.request.Request(f"{YT_API}/{endpoint}?{q}",
                                 headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        _fail_log(log, f"стрим: {endpoint} не ответил: {e!r}")
        return None


def chat_tick(now=None, log=log_default, state_f=None, fetch=None):
    """Чат стрима (раз в CHAT_POLL_EVERY_S, только в режиме стримера).
    -> категория buh/chat (first/active/quiet) или None. liveChatId кэшируется на сессию."""
    global STATE_F
    if state_f is not None:
        STATE_F = state_f
    now = time.monotonic() if now is None else now
    st = load_state()
    if not st.get("chat_id"):
        data = _api_get("liveBroadcasts", {"part": "snippet", "broadcastStatus": "active"}, log, fetch)
        items = (data or {}).get("items") or []
        st["chat_id"] = items[0].get("snippet", {}).get("liveChatId") if items else None
        if not st["chat_id"]:
            log("чат: активного эфира нет — liveChatId не получен")
            save_state(st)
            return None
        log("чат: liveChatId получен (кэш на сессию)")
    data = _api_get("liveChatMessages", {"part": "snippet", "maxResults": 200,
                                         "liveChatId": st["chat_id"]}, log, fetch)
    if data is None:
        save_state(st)
        return None
    n = len(data.get("items") or [])
    ev = None
    if n > 0:
        if not st.get("chat_first"):
            ev, st["chat_first"] = "first", True
            log("чат: первое сообщение сессии — first")
        st["chat_quiet_since"] = now
        if n >= CHAT_ACTIVE_N and now - st.get("chat_active_ann", 0.0) >= CHAT_ACTIVE_COOL_S:
            st["chat_active_ann"] = now
            if ev is None:
                ev = "active"
            log(f"чат: {n} сообщений за тик — active")
    else:
        quiet_for = now - st.get("chat_quiet_since", 0.0)
        if (st.get("viewers") or 0) > 0 and quiet_for >= CHAT_QUIET_AFTER_S \
                and now - st.get("chat_quiet_ann", 0.0) >= CHAT_QUIET_COOL_S:
            st["chat_quiet_ann"] = now
            ev = "quiet"
            log(f"чат: тишина {quiet_for / 60:.0f} мин при зрителях — quiet")
        else:
            _fail_log(log, f"чат: тишина {quiet_for / 60:.0f} мин — повода нет")
    save_state(st)
    return ev


def subs_tick(now=None, log=log_default, state_f=None, fetch=None):
    """Подписчики канала (раз в SUBS_POLL_EVERY_S). -> 'subs' при приросте с начала стрима,
    не чаще раза в SUBS_MIN_GAP_S; число не озвучиваем."""
    global STATE_F
    if state_f is not None:
        STATE_F = state_f
    now = time.monotonic() if now is None else now
    st = load_state()
    data = _api_get("channels", {"part": "statistics", "mine": "true"}, log, fetch)
    items = (data or {}).get("items") or []
    if not items:
        return None
    try:
        subs = int(items[0].get("statistics", {}).get("subscriberCount"))
    except (TypeError, ValueError):
        return None
    if st.get("subs_start") is None:
        st["subs_start"] = subs
        save_state(st)
        log(f"подписчики: база сессии {subs}")
        return None
    if subs > st["subs_start"] and now - st.get("subs_ann", 0.0) >= SUBS_MIN_GAP_S:
        st["subs_ann"] = now
        save_state(st)
        log(f"подписчики: +{subs - st['subs_start']} с начала стрима — subs")
        return "subs"
    if subs > st["subs_start"]:
        log(f"подписчики: прирост есть, но звучал {(now - st.get('subs_ann', 0.0)) / 60:.0f} мин назад — молчим")
    save_state(st)
    return None


def superchat_tick(now=None, log=log_default, state_f=None, fetch=None):
    """Super Chat (раз в SUPERCHAT_POLL_EVERY_S). Дедуп по id в state. 403 -> лог один раз,
    метрика отключается (скоупа не хватает), пилот целиком живёт."""
    global STATE_F
    if state_f is not None:
        STATE_F = state_f
    st = load_state()
    if st.get("sc_off"):
        return None
    def _fetch_403(endpoint, params):
        if fetch is not None:
            return fetch(endpoint, params)
        try:
            return _api_get(endpoint, params, log)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return {"__403__": True}
            raise
    data = _fetch_403("superChatEvents", {"part": "snippet", "maxResults": 5}, )
    if data is None:
        return None
    if data.get("__403__"):
        st["sc_off"] = True
        save_state(st)
        log("superchat: 403 insufficientPermissions — скоупа нет, метрика отключена "
            "(нужен youtube.force-ssl; не трогаем остальной пилот)")
        return None
    seen = st.get("sc_seen") or []
    fresh = [i for i in (data.get("items") or []) if i.get("id") not in seen]
    if fresh:
        st["sc_seen"] = (seen + [i.get("id") for i in fresh])[-100:]   # хвост ограничен
        save_state(st)
        log(f"superchat: {len(fresh)} новых — superchat")
        return "superchat"
    save_state(st)
    return None


def note_donation(now=None, state_f=None):
    """cb_radio зовёт при событии donation_pilot: метка времени для after_donation-питча."""
    global STATE_F
    if state_f is not None:
        STATE_F = state_f
    now = time.monotonic() if now is None else now
    st = load_state()
    st.update(donation_last=now, after_roll=None, pitch_after_done=False)
    save_state(st)


def pitch_tick(now=None, log=log_default, state_f=None, rnd=None):
    """Питч донатов (раз в ~минуту из cb_radio, только в режиме стримера).
    -> категория buh/donate_pitch (economy/viewers_no_donations/after_donation/norm) или None.
    Общий заслон: любой питч не чаще раза в 15-18 мин; донат за последние 15 мин глушит
    economy и viewers_no_donations. Каждое решение — в лог с причиной (правило 7)."""
    global STATE_F
    if state_f is not None:
        STATE_F = state_f
    now = time.monotonic() if now is None else now
    st = load_state()
    rnd = rnd or random.Random(st.get("seed"))
    kind, reason = None, None
    recent_donation = now - st.get("donation_last", 0.0) <= PITCH_KIND_WINDOW_S
    # кандидаты по приоритету: after_donation > viewers_no_donations > economy > norm
    if st.get("donation_last") and PITCH_AFTER_MIN_S <= now - st["donation_last"] <= PITCH_AFTER_MAX_S:
        if not st.get("pitch_after_done"):
            if st.get("after_roll") is None:
                st["after_roll"] = rnd.random()
            if st["after_roll"] < PITCH_AFTER_P:
                kind = "after_donation"
                st["pitch_after_done"] = True
                reason = "минута-две после доната, бросок за питч"
            else:
                st["pitch_after_done"] = True
                reason = "минута-две после доната, бросок против питча — молчим"
    if kind is None and not recent_donation:
        if st.get("pitch_economy_next", 0.0) <= now:
            if now - st.get("donation_last", 0.0) >= PITCH_NO_DON_AFTER_S and (st.get("viewers") or 0) >= 5:
                kind = "viewers_no_donations"
                reason = f"зрителей {st.get('viewers')} ≥5, донатов не было " \
                         f"{(now - st.get('donation_last', 0.0)) / 60:.0f} мин"
            else:
                kind = "economy"
                reason = "таймер 15-18 мин, донатов давно не было"
            st["pitch_economy_next"] = now + PITCH_GAP_MIN_S + rnd.random() * PITCH_GAP_JITTER_S
    elif kind is None:
        reason = "донат меньше 15 мин назад — economy/viewers_no_donations пропускаем (не канючим на волне щедрости)"
    if kind is None and st.get("pitch_norm_next", 0.0) <= now:
        kind = "norm"
        reason = "норматив ~45 мин"
        st["pitch_norm_next"] = now + PITCH_NORM_EVERY_S
    if kind is not None:
        gap = now - st.get("pitch_last", 0.0)
        min_gap = PITCH_GAP_MIN_S + (PITCH_GAP_JITTER_S if kind in ("economy", "viewers_no_donations") else 0.0)
        if gap < min_gap:
            # заслон не пропускает: повтор через минимальный гэп (а не через полный интервал —
            # иначе gated-норматив «уезжал» бы на 45 мин и звучал бы почти никогда)
            st["pitch_norm_next"] = now + PITCH_GAP_MIN_S
            if kind in ("economy", "viewers_no_donations"):
                st["pitch_economy_next"] = now + PITCH_GAP_MIN_S
            log(f"питч: {kind} отложен — звучал {gap / 60:.1f} мин назад, заслон 15-18 мин")
            save_state(st)
            return None
        st["pitch_last"] = now
        log(f"питч: {kind} — {reason}")
        save_state(st)
        return kind
    if reason:
        log(f"питч: молчим — {reason}")
    save_state(st)
    return None
