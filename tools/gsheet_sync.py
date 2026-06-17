"""커리큘럼·지식 인덱스를 Google Sheets에 한 방에 동기화한다.

"커리큘럼 시트에 올려줘" 같은 요청이 오면 이 스크립트를 실행한다.
JSON(원본)을 표로 빌드해 지정한 스프레드시트의 탭에 덮어쓴다(단방향 push).

준비물(secrets/ 폴더, .gitignore로 보호됨):
  - secrets/gcp_service_account.json : Google Cloud 서비스 계정 키
  - secrets/spreadsheet_id.txt        : 대상 스프레드시트 ID 한 줄

실행:
    python tools/gsheet_sync.py
"""
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

sys.path.insert(0, str(Path(__file__).parent))
from export_sheets_csv import build_curriculum_rows, build_knowledge_rows

BASE = Path(__file__).parent.parent
KEY_FILE = BASE / "secrets" / "gcp_service_account.json"
ID_FILE = BASE / "secrets" / "spreadsheet_id.txt"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _client() -> gspread.Client:
    if not KEY_FILE.exists():
        raise FileNotFoundError(
            f"서비스 계정 키가 없습니다: {KEY_FILE}\n"
            "Google Cloud에서 서비스 계정 키(JSON)를 받아 이 경로에 두세요."
        )
    creds = Credentials.from_service_account_file(str(KEY_FILE), scopes=SCOPES)
    return gspread.authorize(creds)


def _spreadsheet_id() -> str:
    if not ID_FILE.exists():
        raise FileNotFoundError(
            f"스프레드시트 ID 파일이 없습니다: {ID_FILE}\n"
            "빈 Google Sheets를 만들어 서비스 계정에 공유한 뒤, URL의 ID를 이 파일에 적으세요."
        )
    return ID_FILE.read_text(encoding="utf-8").strip()


def _push(sh: gspread.Spreadsheet, tab: str, fields: list[str], rows: list[dict]) -> int:
    try:
        ws = sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=max(len(rows) + 10, 50), cols=len(fields) + 2)
    ws.clear()
    values = [fields] + [[str(r.get(f, "")) for f in fields] for r in rows]
    ws.update(values=values, range_name="A1")
    # 헤더 굵게 + 첫 행 고정
    ws.format("A1:Z1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)
    return len(rows)


def sync() -> str:
    gc = _client()
    sh = gc.open_by_key(_spreadsheet_id())
    n1 = _push(sh, "커리큘럼_세션", *build_curriculum_rows())
    n2 = _push(sh, "지식_자료", *build_knowledge_rows())
    print(f"동기화 완료: 커리큘럼 세션 {n1}행, 지식 자료 {n2}행")
    print(f"시트 URL: {sh.url}")
    return sh.url


if __name__ == "__main__":
    sync()
