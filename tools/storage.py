"""데이터 저장소 추상화 계층 — 로컬 폴더 / 구글 드라이브 두 백엔드.

이 앱의 모든 데이터(JSON 인덱스·지식 .md·커리큘럼·뉴스·소스 등)는 평소
`data/` 폴더에 있다. 그런데 `data/`는 PC에서 구글 공유 드라이브를 가리키는
정션이라, PC가 없는 클라우드(Streamlit Cloud)에서는 보이지 않는다.

그래서 데이터 접근을 **이 모듈 하나로 모은다.** tools/ 모듈과 app.py는 직접
파일을 열지 말고 storage.read_json / write_json / ... 을 호출한다. 그러면
실행 환경에 따라 통로만 바뀐다:

  - **로컬(PC)**     : `data/` 폴더를 그대로 읽고 쓴다 (기존과 100% 동일).
  - **클라우드**     : 같은 파일들을 구글 드라이브 API로 읽고 쓴다.

백엔드는 자동 선택된다:
  1) 환경변수 `CLAUDEHELPER_STORAGE` 가 "drive" 또는 "local" 이면 그대로.
  2) 아니면, 드라이브 설정(서비스계정 + 폴더ID)이 갖춰져 있으면 drive,
     없으면 local (기본).

경로 규약: 모든 함수는 `data/` 기준 **상대경로**를 받는다.
  예) "knowledge_db.json", "curricula/foo.json", "knowledge/bar.md"
슬래시(/)로 폴더를 구분한다(윈도우에서도 슬래시 사용).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# data/ 의 로컬 위치 (정션이면 정션을 따라간다)
DATA_ROOT = Path(__file__).resolve().parent.parent / "data"


# ── 백엔드 선택 ────────────────────────────────────────────────
def _drive_config() -> dict | None:
    """드라이브 백엔드 설정을 모은다. 못 갖추면 None.

    설정 출처(우선순위):
      - Streamlit secrets: st.secrets["gcp_service_account"] (dict) +
        st.secrets["drive_folder_id"]
      - 로컬 파일: secrets/gcp_service_account.json +
        secrets/drive_folder_id.txt
    """
    info = None
    folder_id = None

    # 1) Streamlit secrets (클라우드 배포 환경)
    try:
        import streamlit as st  # noqa: PLC0415

        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            folder_id = st.secrets.get("drive_folder_id", "") or None
    except Exception:
        pass

    # 2) 로컬 secrets/ 파일 (PC에서 드라이브 모드 테스트할 때)
    base = Path(__file__).resolve().parent.parent / "secrets"
    if info is None:
        key = base / "gcp_service_account.json"
        if key.exists():
            try:
                info = json.loads(key.read_text(encoding="utf-8"))
            except Exception:
                info = None
    if folder_id is None:
        fid = base / "drive_folder_id.txt"
        if fid.exists():
            folder_id = fid.read_text(encoding="utf-8").strip() or None

    if info and folder_id:
        return {"info": info, "folder_id": folder_id}
    return None


def _select_backend() -> str:
    forced = os.environ.get("CLAUDEHELPER_STORAGE", "").strip().lower()
    if forced in ("local", "drive"):
        if forced == "drive" and _drive_config() is None:
            # drive 강제인데 설정이 없으면 안전하게 local 로 떨어진다.
            return "local"
        return forced
    return "drive" if _drive_config() is not None else "local"


_BACKEND: "_Backend | None" = None


def backend() -> "_Backend":
    """현재 백엔드 인스턴스(싱글턴)를 반환한다."""
    global _BACKEND
    if _BACKEND is None:
        if _select_backend() == "drive":
            _BACKEND = _DriveBackend(_drive_config())
        else:
            _BACKEND = _LocalBackend()
    return _BACKEND


def backend_name() -> str:
    return "drive" if isinstance(backend(), _DriveBackend) else "local"


# ── 공개 API (모든 모듈이 이걸 쓴다) ────────────────────────────
def read_text(relpath: str, default: str | None = None) -> str | None:
    return backend().read_text(relpath, default)


def write_text(relpath: str, content: str) -> None:
    backend().write_text(relpath, content)


def read_bytes(relpath: str) -> bytes | None:
    return backend().read_bytes(relpath)


def write_bytes(relpath: str, content: bytes) -> None:
    backend().write_bytes(relpath, content)


def read_json(relpath: str, default=None):
    raw = read_text(relpath)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return default


def write_json(relpath: str, obj) -> None:
    write_text(relpath, json.dumps(obj, ensure_ascii=False, indent=2))


def list_dir(relpath: str, suffixes: tuple[str, ...] | None = None) -> list[str]:
    """폴더 안 파일들의 **상대경로 목록**을 정렬해 반환(폴더 자체 제외).

    suffixes 예: (".md",) / (".txt", ".md", ".pdf"). None이면 전체.
    """
    return backend().list_dir(relpath, suffixes)


def exists(relpath: str) -> bool:
    return backend().exists(relpath)


def delete(relpath: str) -> None:
    backend().delete(relpath)


def to_relpath(path) -> str:
    """저장돼 있던 어떤 형식의 경로든 storage 상대경로로 정규화한다.

    기존 데이터에는 경로가 절대(C:\\...\\data\\knowledge\\x.md), 슬래시/역슬래시,
    'data/...' 접두 등 제각각으로 섞여 있다. 'data' 폴더 이후 부분만 취해
    "knowledge/x.md" 같은 상대경로로 통일한다.
    """
    p = str(path).replace("\\", "/")
    for marker in ("/data/", "data/"):
        idx = p.find(marker)
        if idx != -1:
            return p[idx + len(marker):]
    return p.lstrip("/")


def local_path(relpath: str) -> Path:
    """로컬 파일 경로가 꼭 필요한 코드용(예: PPTX 생성, 업로드 임시저장).

    로컬 백엔드에선 실제 data/ 경로. 드라이브 백엔드에선 컨테이너의
    임시 미러 경로를 돌려준다(읽기 전이면 먼저 드라이브에서 받아온다).
    되도록 read_*/write_* 를 쓰고, 이 함수는 외부 라이브러리가 경로를
    요구할 때만 쓴다.
    """
    return backend().local_path(relpath)


# ── 백엔드 구현 ────────────────────────────────────────────────
class _Backend:
    def read_text(self, relpath: str, default: str | None = None) -> str | None: ...
    def write_text(self, relpath: str, content: str) -> None: ...
    def read_bytes(self, relpath: str) -> bytes | None: ...
    def write_bytes(self, relpath: str, content: bytes) -> None: ...
    def list_dir(self, relpath: str, suffixes) -> list[str]: ...
    def exists(self, relpath: str) -> bool: ...
    def delete(self, relpath: str) -> None: ...
    def local_path(self, relpath: str) -> Path: ...


class _LocalBackend(_Backend):
    """data/ 폴더를 직접 읽고 쓰는 기존 동작."""

    def _p(self, relpath: str) -> Path:
        return DATA_ROOT / relpath

    def read_text(self, relpath, default=None):
        p = self._p(relpath)
        if not p.exists():
            return default
        return p.read_text(encoding="utf-8")

    def write_text(self, relpath, content):
        p = self._p(relpath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def read_bytes(self, relpath):
        p = self._p(relpath)
        if not p.exists():
            return None
        return p.read_bytes()

    def write_bytes(self, relpath, content):
        p = self._p(relpath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

    def list_dir(self, relpath, suffixes):
        d = self._p(relpath)
        if not d.exists():
            return []
        out = []
        for f in d.iterdir():
            if not f.is_file():
                continue
            if suffixes and f.suffix.lower() not in suffixes:
                continue
            out.append(f"{relpath.rstrip('/')}/{f.name}")
        return sorted(out)

    def exists(self, relpath):
        return self._p(relpath).exists()

    def delete(self, relpath):
        p = self._p(relpath)
        if p.exists():
            p.unlink()

    def local_path(self, relpath):
        p = self._p(relpath)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


class _DriveBackend(_Backend):
    """구글 드라이브를 data/ 폴더처럼 쓰는 백엔드.

    relpath 의 폴더 부분을 드라이브 폴더 트리로 해석하고(없으면 생성),
    파일 이름으로 파일을 찾아 읽고/덮어쓴다. 공유 드라이브도 지원
    (supportsAllDrives=True). 파일ID는 캐싱한다.
    """

    def __init__(self, cfg: dict):
        self._cfg = cfg
        self._svc = None
        self._root_id = cfg["folder_id"]
        self._folder_cache: dict[str, str] = {"": self._root_id}
        self._file_cache: dict[str, str | None] = {}
        self._tmp = Path(os.environ.get("TEMP", "/tmp")) / "claudehelper_drive"

    # -- 구글 드라이브 서비스 (지연 로딩) --
    def _service(self):
        if self._svc is None:
            from google.oauth2.service_account import Credentials  # noqa: PLC0415
            from googleapiclient.discovery import build  # noqa: PLC0415

            scopes = ["https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(self._cfg["info"], scopes=scopes)
            self._svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._svc

    def _files(self):
        return self._service().files()

    # -- 폴더/파일 경로 해석 --
    def _split(self, relpath: str) -> tuple[str, str]:
        relpath = relpath.strip("/")
        if "/" in relpath:
            folder, name = relpath.rsplit("/", 1)
            return folder, name
        return "", relpath

    def _folder_id(self, folder: str, create: bool = False) -> str | None:
        folder = folder.strip("/")
        if folder in self._folder_cache:
            return self._folder_cache[folder]
        parent_path, name = self._split(folder) if "/" in folder else ("", folder)
        parent_id = self._folder_id(parent_path, create) if parent_path else self._root_id
        if parent_id is None:
            return None
        q = (
            f"'{parent_id}' in parents and name = '{name}' and "
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        res = self._files().list(
            q=q, fields="files(id)", supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        items = res.get("files", [])
        if items:
            fid = items[0]["id"]
        elif create:
            meta = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }
            fid = self._files().create(
                body=meta, fields="id", supportsAllDrives=True,
            ).execute()["id"]
        else:
            fid = None
        if fid is not None:
            self._folder_cache[folder] = fid
        return fid

    def _file_id(self, relpath: str) -> str | None:
        relpath = relpath.strip("/")
        if relpath in self._file_cache:
            return self._file_cache[relpath]
        folder, name = self._split(relpath)
        parent_id = self._folder_id(folder)
        if parent_id is None:
            self._file_cache[relpath] = None
            return None
        q = f"'{parent_id}' in parents and name = '{name}' and trashed = false"
        res = self._files().list(
            q=q, fields="files(id)", supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        items = res.get("files", [])
        fid = items[0]["id"] if items else None
        self._file_cache[relpath] = fid
        return fid

    # -- 읽기/쓰기 --
    def read_bytes(self, relpath):
        fid = self._file_id(relpath)
        if fid is None:
            return None
        from googleapiclient.http import MediaIoBaseDownload  # noqa: PLC0415
        import io  # noqa: PLC0415

        buf = io.BytesIO()
        req = self._files().get_media(fileId=fid, supportsAllDrives=True)
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        return buf.getvalue()

    def read_text(self, relpath, default=None):
        data = self.read_bytes(relpath)
        if data is None:
            return default
        return data.decode("utf-8")

    def write_bytes(self, relpath, content: bytes):
        from googleapiclient.http import MediaIoBaseUpload  # noqa: PLC0415
        import io  # noqa: PLC0415

        folder, name = self._split(relpath)
        parent_id = self._folder_id(folder, create=True)
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/octet-stream",
                                  resumable=False)
        fid = self._file_id(relpath)
        if fid:
            self._files().update(fileId=fid, media_body=media,
                                 supportsAllDrives=True).execute()
        else:
            meta = {"name": name, "parents": [parent_id]}
            new = self._files().create(body=meta, media_body=media, fields="id",
                                       supportsAllDrives=True).execute()
            self._file_cache[relpath.strip("/")] = new["id"]

    def write_text(self, relpath, content: str):
        self.write_bytes(relpath, content.encode("utf-8"))

    def list_dir(self, relpath, suffixes):
        parent_id = self._folder_id(relpath.strip("/"))
        if parent_id is None:
            return []
        out = []
        page = None
        while True:
            res = self._files().list(
                q=f"'{parent_id}' in parents and trashed = false",
                fields="nextPageToken, files(name, mimeType)",
                supportsAllDrives=True, includeItemsFromAllDrives=True,
                pageToken=page,
            ).execute()
            for f in res.get("files", []):
                if f["mimeType"] == "application/vnd.google-apps.folder":
                    continue
                name = f["name"]
                if suffixes and not any(name.lower().endswith(s) for s in suffixes):
                    continue
                out.append(f"{relpath.rstrip('/')}/{name}")
            page = res.get("nextPageToken")
            if not page:
                break
        return sorted(out)

    def exists(self, relpath):
        return self._file_id(relpath) is not None

    def delete(self, relpath):
        fid = self._file_id(relpath)
        if fid:
            self._files().delete(fileId=fid, supportsAllDrives=True).execute()
            self._file_cache[relpath.strip("/")] = None

    def local_path(self, relpath):
        """드라이브 내용을 임시 파일로 내려받아 그 경로를 준다(읽기용)."""
        p = self._tmp / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.read_bytes(relpath)
        if data is not None:
            p.write_bytes(data)
        return p
