# -*- coding: utf-8 -*-
"""Личное уведомление пользователю в Telegram (бот → личка, НЕ канал).

  python notify_me.py "текст сообщения"

Читает promo/telegram/bot_token.txt и promo/donations/tg_chat_id.txt.
Правило: только по делу — дыры контент-плана, упавшие задачи, ответы внешних
сервисов, вопросы-блокеры. Суммы/доход — можно сюда (личка), никогда — в канал.
"""
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
TOKEN_F = ROOT / "telegram" / "bot_token.txt"
CHAT_F = ROOT / "donations" / "tg_chat_id.txt"


def notify(text):
    token = TOKEN_F.read_text(encoding="utf-8").strip()
    chat = CHAT_F.read_text(encoding="utf-8").strip()
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": text}, timeout=30).json()
    if not r.get("ok"):
        sys.exit(f"TG sendMessage: {r}")
    return r["result"]["message_id"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    print(f"отправлено, message_id={notify(sys.argv[1])}")
