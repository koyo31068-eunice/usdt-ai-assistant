"""
데이터 API (CRUD 4개 + summary 1개)
  POST   /api/data            새 데이터 추가
  GET    /api/data            데이터 목록 조회
  GET    /api/data/summary    데이터 요약 (AI 프롬프트 주입용)
  PUT    /api/data/{id}       데이터 수정
  DELETE /api/data/{id}       데이터 삭제
"""
import time

from fastapi import APIRouter, HTTPException, Query
from firebase_admin import firestore

from config import DATA_COLLECTION
from db import get_db
from schemas import DataCreate, DataOut, DataUpdate
from summary import compute_summary

router = APIRouter(prefix="/api/data", tags=["데이터"])

# ---------------- 요약 캐시 ----------------
# 채팅할 때마다 240건을 다시 읽으면 Firestore 읽기 횟수가 빨리 늘어나므로,
# 요약을 5분간 메모리에 보관하고, 데이터가 추가/수정/삭제되면 즉시 버립니다.
_CACHE = {"value": None, "at": 0.0}
CACHE_SECONDS = 300


def invalidate_summary():
    _CACHE["value"] = None


def _iso(ts):
    return ts.isoformat() if hasattr(ts, "isoformat") else (str(ts) if ts else None)


def _num(v):
    return int(v) if isinstance(v, float) and v.is_integer() else v


def doc_to_dict(doc):
    d = doc.to_dict() or {}
    return {
        "id": doc.id,
        "date": d.get("date", ""),
        "value": _num(d.get("value", 0)),
        "memo": d.get("memo", ""),
        "source": d.get("source"),
        "created_at": _iso(d.get("created_at")),
        "updated_at": _iso(d.get("updated_at")),
    }


def get_summary(force: bool = False):
    """다른 모듈(채팅 API)에서도 사용하는 요약 함수"""
    if not force and _CACHE["value"] and time.time() - _CACHE["at"] < CACHE_SECONDS:
        return _CACHE["value"]
    docs = get_db().collection(DATA_COLLECTION).order_by("date").stream()
    rows = [doc_to_dict(d) for d in docs]
    summary = compute_summary(rows)
    _CACHE.update(value=summary, at=time.time())
    return summary


def _get_existing(doc_id: str):
    ref = get_db().collection(DATA_COLLECTION).document(doc_id)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail=f"데이터를 찾을 수 없습니다: {doc_id}")
    return ref


# ---------------- 엔드포인트 ----------------
# ⚠ /summary 를 /{id} 보다 먼저 선언해야 'summary'가 id로 오인되지 않습니다.
@router.get("/summary", summary="데이터 요약 (AI 프롬프트 주입용)")
def data_summary(refresh: bool = Query(False, description="true면 캐시를 무시하고 다시 계산")):
    try:
        return get_summary(force=refresh)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"요약 계산 실패: {e}")


@router.get("", response_model=list[DataOut], summary="데이터 목록 조회")
def list_data(
    limit: int = Query(500, ge=1, le=1000, description="최대 개수 (1~1000)"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="asc: 오래된 순, desc: 최신 순"),
):
    direction = firestore.Query.ASCENDING if order == "asc" else firestore.Query.DESCENDING
    try:
        docs = (get_db().collection(DATA_COLLECTION)
                .order_by("date", direction=direction).limit(limit).stream())
        return [doc_to_dict(d) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"목록 조회 실패: {e}")


@router.post("", response_model=DataOut, status_code=201, summary="새 데이터 추가")
def create_data(body: DataCreate):
    try:
        ref = get_db().collection(DATA_COLLECTION).document()      # 자동 ID
        data = body.model_dump()
        data["value"] = _num(data["value"])                        # 1357.0 → 1357
        ref.set({
            **data,
            "source": "api",
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })
        invalidate_summary()
        return doc_to_dict(ref.get())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"저장 실패: {e}")


@router.put("/{doc_id}", response_model=DataOut, summary="데이터 수정")
def update_data(doc_id: str, body: DataUpdate):
    ref = _get_existing(doc_id)
    changes = body.model_dump(exclude_none=True)
    if "value" in changes:
        changes["value"] = _num(changes["value"])
    changes["updated_at"] = firestore.SERVER_TIMESTAMP
    try:
        ref.update(changes)
        invalidate_summary()
        return doc_to_dict(ref.get())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수정 실패: {e}")


@router.delete("/{doc_id}", summary="데이터 삭제")
def delete_data(doc_id: str):
    ref = _get_existing(doc_id)
    try:
        ref.delete()
        invalidate_summary()
        return {"deleted": doc_id, "message": "삭제되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"삭제 실패: {e}")