# -*- coding: utf-8 -*-
"""22.11 one-off: Opus (anthropic/claude-opus-4.5) проверяет идиоматичность ответов наших
водителей проезжим (живой CB-жаргон, не учебник). Только правки, где звучит неестественно.
  G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/check_opus_foreign80.py
"""
import json
import os
import urllib.request
from pathlib import Path

KEY = (Path(__file__).resolve().parents[1] / "openrouter_key.txt").read_text().strip()

ANSWERS = {
 "yanek_pl": [
  ("radio", "Ładnie słychać, czysto leci, piątka z radiem!"),
  ("thanks", "Nie ma za co, bracie, szerokiej i do zobaczenia na obwodnicy!"),
  ("warn", "Dzięki za info, kurna, zwolnię i się rozglądam!"),
  ("bye", "No to do zobaczenia, kolego, piątka i szerokiej!"),
  ("rant", "U nas to samo, kurwa, jeszcze się taki nie urodził, co by ich poukładał!")],
 "yanek_en": [
  ("radio", "Loud and clear, brother, five by five!"),
  ("thanks", "Anytime, mate, keep it rubber side down!"),
  ("warn", "Copy that, slowing down, eyes open!"),
  ("bye", "Catch you later, driver, safe miles!")],
 "professor_de": [
  ("radio", "Verstanden, Sie kommen laut und deutlich, fünf mal fünf."),
  ("warn", "Danke für die Meldung, ich passe auf und fahre entsprechend."),
  ("rant", "Das ist leider überall so, Kollege, der Beruf wird nicht leichter."),
  ("bye", "Alles Gute, gute Heimfahrt und keine Strafzettel."),
  ("thanks", "Gern geschehen, Kollege, man hilft sich ja auf der Straße.")],
 "professor_en": [
  ("radio", "Five by five, you're coming through perfectly."),
  ("warn", "Message received, I'll keep an eye out."),
  ("rant", "Same story here, colleague. The regulations aren't getting any fewer."),
  ("bye", "Safe journey home, and do watch your speed.")],
 "sova_fr": [
  ("radio", "Vous passez très bien, cinq sur cinq, mon ami."),
  ("warn", "Merci pour l'information, je roulerai prudemment."),
  ("rant", "C'est partout pareil, hélas... Courage, collègue."),
  ("bye", "Bonne route à vous, et douce nuit si vous roulez tard."),
  ("thanks", "Je vous en prie. On se rend service entre routiers.")],
 "rustam_tr": [
  ("warn", "Sağ ol kardeşim, dikkat ediyorum!"),
  ("radio", "İyi duyuyorum, beş üzerinden beş!"),
  ("bye", "Görüşürüz kardeşim, selametle!"),
  ("thanks", "Rica ederim kardeşim, yol açık olsun!"),
  ("rant", "Aynı bizde de var, vay, bu yollar hep böyle!")],
 "bahti_tr": [
  ("warn", "Oldum kardeşim, yavaş gidiyorum!"),
  ("radio", "Seni duyuyorum, iyi, iyi!"),
  ("bye", "Hoşça kal abi, yolun açık olsun!"),
  ("rant", "Tam anlamadım ama... çay koydum, tamam!")],
}

prompt = """Ты — носитель семи языков: польского, английского (британский CB-слэнг дальнобойщиков), немецкого, французского, турецкого. Проверь реплики русских дальнобойщиков, отвечающих по рации проезжим европейцам на их языке.

Требования: живой радиожаргон дальнобойщика этой страны (CB-радио, канал 19), НЕ учебник и не деловой язык. Коротко, 1 фраза. Персонажи:
- yanek: поляк, тёплый, душевный, «bracie», словечки «kurna/kurwa» — норма.
- professor: немец, точный, чуть книжный, но не чужой эфиру.
- sova: француз, мягко, с достоинством.
- rustam: узбек, говорит по-турецки просто, «kardeşim», «vay».
- bahti: младший брат Рустама, турок, совсем простые фразы.

Для каждой реплики: если звучит естественно — верни как есть; если нет — исправь (CB-жаргон). Ответ строго JSON: {"ключ": [[тип, "исправленный текст"], ...]} без пояснений.

""" + json.dumps(ANSWERS, ensure_ascii=False)

body = {"model": "anthropic/claude-opus-4.5", "messages": [{"role": "user", "content": prompt}]}
req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
                             data=json.dumps(body).encode(), headers={
                                 "Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
d = json.loads(urllib.request.urlopen(req, timeout=180).read())
print("cost: $", d.get("usage", {}).get("cost"))
out = d["choices"][0]["message"]["content"]
out = out[out.index("{"):out.rindex("}") + 1]
fixed = json.loads(out)
for k, lines in ANSWERS.items():
    for (t0, orig), (t1, new) in zip(lines, fixed[k]):
        mark = "  <-- ИЗМЕНЕНО" if new != orig else ""
        print(f"{k}:{t0}  {orig}  ->  {new}{mark}")
