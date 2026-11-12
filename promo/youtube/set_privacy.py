"""Смена видимости ролика на YouTube (Канал 15). Токен общий с upload_short.py.

Пример:
  python set_privacy.py 8jCJsdIpG5M --privacy public
  python set_privacy.py 8jCJsdIpG5M --check     # только показать текущий статус
"""
import argparse
import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

HERE = Path(__file__).resolve().parent
SECRET = HERE / "client_secret.json"
TOKEN = HERE / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube"]


def youtube():
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
        if creds and not set(SCOPES) <= set(creds.scopes or []):
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds or not creds.valid:
            creds = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES).run_local_server(port=0)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video_id")
    p.add_argument("--privacy", choices=["private", "unlisted", "public"])
    p.add_argument("--check", action="store_true")
    a = p.parse_args()

    yt = youtube()
    cur = yt.videos().list(part="status,snippet", id=a.video_id).execute()
    if not cur.get("items"):
        sys.exit(f"ролик не найден: {a.video_id}")
    item = cur["items"][0]
    print(json.dumps({"id": a.video_id, "title": item["snippet"]["title"],
                      "privacy": item["status"]["privacyStatus"]}, ensure_ascii=False))

    if a.check or not a.privacy:
        return
    yt.videos().update(
        part="status",
        body={"id": a.video_id,
              "status": {"privacyStatus": a.privacy, "selfDeclaredMadeForKids": False}},
    ).execute()
    after = yt.videos().list(part="status", id=a.video_id).execute()
    print(json.dumps({"id": a.video_id, "privacy": after["items"][0]["status"]["privacyStatus"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
