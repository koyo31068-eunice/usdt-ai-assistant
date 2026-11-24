"""
환경 변수 읽기
- 로컬: backend/.env 파일에서 읽음
- Render: 대시보드에 입력한 환경 변수에서 읽음 (.env 파일 없음)
※ 이 파일에는 키 값을 절대 직접 쓰지 않습니다. 실제 값은 .env 또는 Render 환경 변수에만 넣습니다.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")          # 파일이 없으면(Render) 조용히 넘어감

APP_NAME = "USDT AI 비서 API"
APP_VERSION = "1.0.0"

# CORS 허용 도메인 목록: "a,b,c" → ["a", "b", "c"]
ALLOWED_ORIGINS = [
    o.strip().rstrip("/")
    for o in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500").split(",")
    if o.strip()
]


# ---------------- Firebase ----------------
# 로컬: 키 파일 경로 / Render: JSON 내용을 통째로 환경 변수에 넣음 (둘 중 하나)
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()

# Firestore 컬렉션 이름
DATA_COLLECTION = "data"
CONV_COLLECTION = "conversations"


# ---------------- OpenAI ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip() or "gpt-4.1-mini"
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "600"))           # 답변 최대 길이 (비용 제한)
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "").strip()  # 추론형 모델일 때만: minimal/low
CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", "10"))         # GPT에 보낼 이전 메시지 수
CHAT_DAILY_LIMIT = int(os.getenv("CHAT_DAILY_LIMIT", "200"))            # 하루 최대 채팅 요청 수 (과금 보호)