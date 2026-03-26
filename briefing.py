#!/usr/bin/env python3
"""
Daily briefing script: reads Google Calendar events and generates
a morning briefing using Claude API.
"""

import os
import json
import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import anthropic

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
BASE_DIR = Path(__file__).parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"


def get_calendar_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not TOKEN_FILE.exists():
                raise RuntimeError(
                    "未認証\n"
                    "初回認証が必要です。以下のコマンドを実行してください:\n"
                    "  python /home/user/gdp-dashboard/briefing.py --auth"
                )
            raise RuntimeError("認証トークンが無効です。--auth で再認証してください。")
        TOKEN_FILE.write_text(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def run_auth(code=None):
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_FILE), SCOPES, redirect_uri="urn:ietf:wg:oauth:2.0:oob"
    )
    if code:
        flow.fetch_token(code=code)
        TOKEN_FILE.write_text(flow.credentials.to_json())
        print("認証成功！token.json を保存しました。")
        print("次回から Claude Code セッション開始時に自動でブリーフィングが表示されます。")
    else:
        auth_url, _ = flow.authorization_url(prompt="consent")
        print("\n以下のURLをブラウザで開いてGoogleアカウントでログインしてください:\n")
        print(auth_url)
        print("\nログイン後に表示されるコードをコピーして、以下のコマンドを実行してください:")
        print("  python /home/user/gdp-dashboard/briefing.py --auth <コード>")


def fetch_events(service, days_back=7, days_ahead=3):
    now = datetime.datetime.now(datetime.timezone.utc)
    time_min = (now - datetime.timedelta(days=days_back)).isoformat()
    time_max = (now + datetime.timedelta(days=days_ahead)).isoformat()

    result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        maxResults=50,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


def format_events(events):
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    past, upcoming = [], []

    for e in events:
        start = e.get("start", {})
        start_str = start.get("dateTime") or start.get("date", "")
        if not start_str:
            continue

        if "T" in start_str:
            dt = datetime.datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            date = dt.date()
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        else:
            date = datetime.date.fromisoformat(start_str)
            time_str = start_str

        summary = e.get("summary", "(タイトルなし)")
        description = e.get("description", "")
        attendees = [a.get("email", "") for a in e.get("attendees", [])]
        attendee_str = f" (参加者: {', '.join(attendees)})" if attendees else ""

        entry = f"- [{time_str}] {summary}{attendee_str}"
        if description:
            entry += f"\n  メモ: {description[:200]}"

        if date < today:
            past.append(entry)
        else:
            upcoming.append(entry)

    return past, upcoming


def generate_briefing(past_events, upcoming_events):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    today = datetime.date.today().strftime("%Y年%m月%d日")

    past_text = "\n".join(past_events) if past_events else "（過去の予定なし）"
    upcoming_text = "\n".join(upcoming_events) if upcoming_events else "（今後の予定なし）"

    prompt = f"""今日は{today}です。以下のカレンダー情報をもとに、今日の朝のブリーフィングを日本語で作成してください。

## 過去1週間の会議・予定
{past_text}

## 今日〜3日後の予定
{upcoming_text}

以下の3点を簡潔にまとめてください：
1. **今日やること** - 今日の予定と、過去の会議から生まれたフォローアップタスク
2. **考えるべきこと** - 進行中のテーマや懸案事項
3. **注目ポイント** - 今週の重要な予定や締め切り

箇条書きで、読みやすく整理してください。"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def main():
    print("\n📅 おはようございます！今日のブリーフィングを取得中...\n")
    try:
        service = get_calendar_service()
        events = fetch_events(service)
        past, upcoming = format_events(events)
        briefing = generate_briefing(past, upcoming)
        print("=" * 60)
        print(briefing)
        print("=" * 60)
        print()
    except FileNotFoundError:
        print("⚠️  credentials.json が見つかりません。")
        print(f"   {CREDENTIALS_FILE} に保存してください。")
    except Exception as e:
        print(f"⚠️  ブリーフィング取得エラー: {e}")


if __name__ == "__main__":
    import sys
    if "--auth" in sys.argv:
        idx = sys.argv.index("--auth")
        code = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        run_auth(code)
    else:
        main()
