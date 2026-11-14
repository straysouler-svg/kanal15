# -*- coding: utf-8 -*-
"""Ежедневная пробивка чеков самозанятого по донатам DonationAlerts (вариант Б).

  python receipts.py              -> чеки по донатам за ВЧЕРА
  python receipts.py --dry-run    -> показать, что пробил бы (без чеков и TG)
  python receipts.py --date 2026-11-13 -> конкретные сутки (Europe/Moscow)
  python receipts.py --bind-tg    -> получить chat_id из getUpdates и сохранить

Суммы и чеки — ТОЛЬКО в личку пользователю (TG-бот) и локальный receipts.log
(gitignored). Никаких сумм в канал, MODLOG, STATUS, git.

Требования: токен DA (auth_da.py), пакет moy-nalog в build/venv, первый запуск
«Мой налог» интерактивный (телефон + пароль lknpd; пароль задаётся через СМС
в приложении «Мой налог» / lknpd.nalog.ru, раздел входа «по паролю»).
"""
import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
VENV_SITE = ROOT / "build" / "venv" / "Lib" / "site-packages"
sys.path.insert(0, str(VENV_SITE))

DA_TOKEN_F = HERE / "da_token.txt"
STATE_F = HERE / "receipts_state.json"
LOG_F = HERE / "receipts.log"
SESSION_F = HERE / "moynalog_session.json"
TG_TOKEN_F = HERE.parent / "telegram" / "bot_token.txt"
TG_CHAT_F = HERE / "tg_chat_id.txt"
RECEIPT_NAME = "Поддержка автора (донат)"
DONATIONS_URL = "https://www.donationalerts.com/api/v1/alerts/donations"
TG_API = "https://api.telegram.org"


logging.basicConfig(
    filename=LOG_F, filemode="a", level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8",
)
log = logging.getLogger("receipts")


# ---------- DonationAlerts ----------

def da_token():
    if not DA_TOKEN_F.exists():
        sys.exit(
            "Нет da_token.txt — сначала получи токен:\n"
            "  python promo/donations/auth_da.py url\n"
            "  (открой ссылку, разреши, вставь адрес редиректа)\n"
            "  python promo/donations/auth_da.py exchange \"<url из адресной строки>\""
        )
    return DA_TOKEN_F.read_text(encoding="utf-8").strip()


def da_fetch_donations(token):
    """Все донаты (постранично). При 401 — refresh и один повтор."""
    out = []
    page = 1
    while True:
        r = requests.get(DONATIONS_URL, params={"page": page},
                         headers={"Authorization": f"Bearer {token}"}, timeout=60)
        if r.status_code == 401 and page == 1:
            log.info("DA 401 — refresh токена")
            import auth_da
            auth_da.refresh()
            return da_fetch_donations(da_token())
        if r.status_code != 200:
            sys.exit(f"DA donations: HTTP {r.status_code}: {r.text[:200]}")
        batch = r.json().get("data") or []
        out.extend(batch)
        last = int(r.headers.get("X-Last-Page", page))
        if page >= last or not batch:
            break
        page += 1
    return out


def filter_by_day(donations, day):
    res = []
    for d in donations:
        try:
            ts = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        local = ts.astimezone()  # Europe/Moscow — таймзона машины
        if local.date() == day:
            res.append(d)
    return res


# ---------- состояние ----------

def load_state():
    if STATE_F.exists():
        return set(json.loads(STATE_F.read_text(encoding="utf-8")).get("ids", []))
    return set()


def save_state(ids):
    STATE_F.write_text(json.dumps({"ids": sorted(ids)}, ensure_ascii=False),
                       encoding="utf-8")


# ---------- «Мой налог» ----------

async def moynalog_client():
    from moy_nalog import MoyNalog
    from moy_nalog.types import AuthDetails, Token

    if SESSION_F.exists():
        kept = json.loads(SESSION_F.read_text(encoding="utf-8"))
        client = MoyNalog(login=kept.get("login", ""), password="restored-by-refresh")
        # подкидываем сохранённый refresh-токен; access-токен протухший —
        # библиотека сама обновит его по refresh (update_access_token).
        client._api.connection.auth._HttpAuth__auth_data = AuthDetails(
            inn=kept["inn"],
            token=Token(value="", expire_in=datetime.now().astimezone() - timedelta(hours=1),
                        refresh_value=kept["refresh_token"]),
        )
        return client

    print("Первый запуск «Мой налог». Пароль lknpd задаётся через СМС в приложении.")
    phone = input("Телефон lknpd.nalog.ru (+7...): ").strip()
    try:
        import getpass
        password = getpass.getpass("Пароль lknpd: ")
    except (ImportError, OSError):
        password = input("Пароль lknpd: ")
    if not phone or not password:
        sys.exit("пустой телефон/пароль")
    return MoyNalog(login=phone, password=password)


def save_moynalog_session(client):
    details = client.auth_details
    if not details:
        return
    login = ""
    if SESSION_F.exists():
        login = json.loads(SESSION_F.read_text(encoding="utf-8")).get("login", "")
    SESSION_F.write_text(json.dumps({
        "login": login,
        "inn": details.inn,
        "refresh_token": details.token.refresh_value,
    }, ensure_ascii=False), encoding="utf-8")


async def add_receipt(client, amount, when):
    income = await client.add_income(
        name=RECEIPT_NAME, created_at=when, quantity=1, amount=amount)
    return income


# ---------- Telegram ----------

def tg_send(text):
    if not TG_CHAT_F.exists():
        print("Нет tg_chat_id.txt — напиши любое сообщение боту "
              "@kanal15_publisher_bot и запусти receipts.py --bind-tg")
        return False
    token = TG_TOKEN_F.read_text(encoding="utf-8").strip()
    chat_id = TG_CHAT_F.read_text(encoding="utf-8").strip()
    r = requests.post(f"{TG_API}/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": text}, timeout=60)
    return r.status_code == 200


def tg_bind():
    token = TG_TOKEN_F.read_text(encoding="utf-8").strip()
    r = requests.get(f"{TG_API}/bot{token}/getUpdates", timeout=60).json()
    chats = [u for u in r.get("result", []) if u.get("message")]
    if not chats:
        sys.exit("Сообщений боту нет — сначала напиши любое сообщение @kanal15_publisher_bot")
    chat_id = str(chats[-1]["message"]["chat"]["id"])
    TG_CHAT_F.write_text(chat_id, encoding="utf-8")
    print(f"OK: chat_id сохранён в {TG_CHAT_F.name}")


# ---------- основной цикл ----------

async def run(day, dry):
    donations = filter_by_day(da_fetch_donations(da_token()), day)
    done = load_state()
    fresh = [d for d in donations if d["id"] not in done]
    skipped_rub = [d for d in fresh if d.get("currency", "RUB") != "RUB"]

    lines = [f"Чеки за {day.isoformat()} (DonationAlerts)"]
    total = 0.0
    count = 0
    client = None

    for d in fresh:
        if d.get("currency", "RUB") != "RUB":
            log.warning("пропуск не-RUB доната id=%s", d["id"])
            continue
        amount = float(d["amount"])
        ts = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00")).astimezone()
        if dry:
            lines.append(f"• пробил бы: {amount:.2f} ₽ (донат {d['id']})")
            count += 1
            total += amount
            continue
        if client is None:
            client = await moynalog_client()
        try:
            income = await add_receipt(client, amount, ts)
        except Exception as ex:  # noqa: BLE001 — ошибка уходит в лог, цикл продолжается
            log.exception("чек не пробит, донат id=%s: %s", d["id"], ex)
            lines.append(f"• ОШИБКА чека: {amount:.2f} ₽ (донат {d['id']}) — в receipts.log")
            continue
        done.add(d["id"])
        count += 1
        total += amount
        log.info("чек пробит: донат id=%s, approvedReceiptUuid=%s",
                 d["id"], income.approved_receipt_uuid)
        lines.append(f"• чек: {amount:.2f} ₽ (донат {d['id']})")

    if skipped_rub:
        lines.append(f"(пропущено не-RUB: {len(skipped_rub)})")
    if count:
        lines.append(f"Итого: {count} чек(ов) на {total:.2f} ₽")
    else:
        lines.append("Новых донатов нет — чеков не пробито.")

    summary = "\n".join(lines)
    if dry:
        print(summary)
        print("\n(dry-run: чеки не пробиты, сводка не отправлена)")
        return
    save_state(done)
    if client is not None:
        save_moynalog_session(client)
        await client.close()
    log.info("сводка за %s: %s чек(ов) на %.2f ₽", day, count, total)
    if not tg_send(summary):
        log.error("не удалось отправить сводку в TG")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="без чеков и отправки")
    ap.add_argument("--date", metavar="YYYY-MM-DD", help="конкретные сутки (иначе вчера)")
    ap.add_argument("--bind-tg", action="store_true", help="сохранить TG chat_id из getUpdates")
    args = ap.parse_args()

    if args.bind_tg:
        tg_bind()
        return
    day = (date.fromisoformat(args.date) if args.date
           else datetime.now().astimezone().date() - timedelta(days=1))
    asyncio.run(run(day, args.dry_run))


if __name__ == "__main__":
    main()
