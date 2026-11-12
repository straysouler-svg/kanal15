"""Загрузка шортса на YouTube (Канал 15). Первый запуск откроет браузер для входа в Google,
дальше работает сам (token.json рядом). Секреты: client_secret.json и token.json — НЕ в git.

Пример:
  python upload_short.py short.mp4 --title "Название #Shorts" --description "текст" \
      --tags "ets2,канал 15,мультиплеер для интровертов" --privacy unlisted
"""
import argparse
import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

HERE = Path(__file__).resolve().parent
SECRET = HERE / "client_secret.json"
TOKEN = HERE / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def youtube():
    if not SECRET.exists():
        sys.exit(f"нет {SECRET} — скачай из Google Cloud Console (см. Настройка YouTube API.md)")
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES).run_local_server(port=0)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--tags", default="")
    p.add_argument("--privacy", default="unlisted", choices=["private", "unlisted", "public"])
    a = p.parse_args()

    f = Path(a.file)
    if not f.exists():
        sys.exit(f"нет файла: {f}")

    yt = youtube()
    body = {
        "snippet": {
            "title": a.title,
            "description": a.description,
            "tags": [t.strip() for t in a.tags.split(",") if t.strip()],
            "categoryId": "20",  # Gaming
        },
        "status": {"privacyStatus": a.privacy, "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(f), chunksize=8 * 1024 * 1024, resumable=True),
    )
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"залито {int(status.progress() * 100)}%")
    vid = resp["id"]
    print(json.dumps({"id": vid, "url": f"https://youtube.com/shorts/{vid}", "privacy": a.privacy}, ensure_ascii=False))


if __name__ == "__main__":
    main()
