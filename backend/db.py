"""
Firestore 연결
- 서비스 계정 키를 코드에 넣지 않고 환경 변수로 받음
  1순위: FIREBASE_SERVICE_ACCOUNT_JSON  (Render 배포용, JSON 내용 전체)
  2순위: FIREBASE_SERVICE_ACCOUNT_PATH  (로컬용, 키 파일 경로)
"""
import json
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

from config import BASE_DIR, FIREBASE_SERVICE_ACCOUNT_JSON, FIREBASE_SERVICE_ACCOUNT_PATH

_db = None


def _load_credentials():
    if FIREBASE_SERVICE_ACCOUNT_JSON:
        try:
            return credentials.Certificate(json.loads(FIREBASE_SERVICE_ACCOUNT_JSON))
        except json.JSONDecodeError as e:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON 값이 올바른 JSON이 아닙니다.") from e

    if FIREBASE_SERVICE_ACCOUNT_PATH:
        path = Path(FIREBASE_SERVICE_ACCOUNT_PATH)
        if not path.is_absolute():
            path = BASE_DIR / path              # backend 폴더 기준 상대경로
        if not path.exists():
            raise RuntimeError(f"서비스 계정 키 파일을 찾을 수 없습니다: {path}")
        return credentials.Certificate(str(path))

    raise RuntimeError(
        "Firebase 환경 변수가 없습니다. "
        "FIREBASE_SERVICE_ACCOUNT_PATH 또는 FIREBASE_SERVICE_ACCOUNT_JSON 을 설정하세요."
    )


def get_db():
    """Firestore 클라이언트 (처음 한 번만 연결하고 재사용)"""
    global _db
    if _db is None:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(_load_credentials())
        _db = firestore.client()
    return _db


def get_project_id():
    get_db()
    return firebase_admin.get_app().project_id