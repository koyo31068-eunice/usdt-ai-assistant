"""
USDT AI 비서 - FastAPI 메인
실행 (backend 폴더에서):  uvicorn main:app --reload
API 문서:                http://127.0.0.1:8000/docs
"""
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import ALLOWED_ORIGINS, APP_NAME, APP_VERSION, CONV_COLLECTION, DATA_COLLECTION
from db import get_db, get_project_id
from routes_chat import router as chat_router
from routes_conversations import router as conv_router
from routes_data import router as data_router

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "빗썸 USDT/KRW 1시간봉 분석 데이터를 Firestore에 저장하고, "
        "데이터 요약을 근거로 답변하는 AI 비서 API입니다."
    ),
)

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------- 라우터 등록 ----------------
app.include_router(data_router)          # /api/data ...
app.include_router(conv_router)          # /api/conversations ...
app.include_router(chat_router)          # /api/chat


# ---------------- 기본 엔드포인트 ----------------
@app.get("/", tags=["기본"], summary="서비스 안내")
def root():
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["기본"], summary="서버 상태 확인")
def health():
    """프론트엔드가 처음 접속할 때 호출해서 서버가 깨어 있는지 확인합니다 (Render 콜드스타트 대응)."""
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "allowed_origins": ALLOWED_ORIGINS,
    }


@app.get("/health/db", tags=["기본"], summary="Firestore 연결 확인")
def health_db():
    """Firestore에 실제로 접속해 data / conversations 컬렉션을 읽어 봅니다."""
    try:
        db = get_db()
        data_sample = len(db.collection(DATA_COLLECTION).limit(5).get())
        conv_sample = len(db.collection(CONV_COLLECTION).limit(5).get())
        return {
            "firestore": "connected",
            "project_id": get_project_id(),
            "data_docs_sample": data_sample,
            "conversation_docs_sample": conv_sample,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Firestore 연결 실패: {e}")