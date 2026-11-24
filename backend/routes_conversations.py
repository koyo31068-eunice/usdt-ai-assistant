"""
대화 기록 API
  POST   /api/conversations        대화 저장
  GET    /api/conversations        대화 목록 조회  (messages 미포함: 제목·미리보기·개수·시각만)
  GET    /api/conversations/{id}   특정 대화 불러오기 (전체 messages 포함)  ← 요구사항 (A) 방식
  DELETE /api/conversations/{id}   대화 삭제

create_conversation(), append_messages() 는 채팅 API(STEP 6)에서 자동 저장에 재사용합니다.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from firebase_admin import firestore

from config import CONV_COLLECTION
from db import get_db
from schemas import ConversationCreate, ConversationDetail, ConversationListItem

router = APIRouter(prefix="/api/conversations", tags=["대화 기록"])

MAX_MESSAGES = 200          # 문서 1개 크기 제한(1MB)을 넘지 않도록 대화당 메시지 수 제한


def _now():
    return datetime.now(timezone.utc).isoformat()


def _iso(ts):
    return ts.isoformat() if hasattr(ts, "isoformat") else (str(ts) if ts else None)


def _make_title(messages):
    first = next((m["content"] for m in messages if m["role"] == "user"), "새 대화")
    first = " ".join(first.split())
    return first[:30] + ("…" if len(first) > 30 else "")


def _make_preview(messages):
    last = messages[-1]["content"] if messages else ""
    last = " ".join(last.split())
    return last[:60] + ("…" if len(last) > 60 else "")


def _to_item(doc, with_messages=False):
    d = doc.to_dict() or {}
    item = {
        "id": doc.id,
        "title": d.get("title", "새 대화"),
        "preview": d.get("preview", ""),
        "message_count": d.get("message_count", len(d.get("messages", []))),
        "created_at": _iso(d.get("created_at")),
        "updated_at": _iso(d.get("updated_at")),
    }
    if with_messages:
        item["messages"] = d.get("messages", [])
    return item


# ---------------- 다른 모듈에서도 쓰는 함수 ----------------
def create_conversation(messages, title=None):
    """messages: [{"role": "user"|"assistant", "content": "..."}] → 새 대화 문서 id 반환"""
    msgs = [{**m, "created_at": m.get("created_at") or _now()} for m in messages][:MAX_MESSAGES]
    ref = get_db().collection(CONV_COLLECTION).document()
    ref.set({
        "title": (title or "").strip() or _make_title(msgs),
        "messages": msgs,
        "message_count": len(msgs),
        "preview": _make_preview(msgs),
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    })
    return ref.id


def get_conversation_messages(conv_id):
    snap = get_db().collection(CONV_COLLECTION).document(conv_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail=f"대화를 찾을 수 없습니다: {conv_id}")
    return (snap.to_dict() or {}).get("messages", [])


def append_messages(conv_id, new_messages):
    """기존 대화 끝에 메시지 추가 (최근 MAX_MESSAGES 개만 유지)"""
    ref = get_db().collection(CONV_COLLECTION).document(conv_id)
    msgs = get_conversation_messages(conv_id)
    msgs += [{**m, "created_at": m.get("created_at") or _now()} for m in new_messages]
    msgs = msgs[-MAX_MESSAGES:]
    ref.update({
        "messages": msgs,
        "message_count": len(msgs),
        "preview": _make_preview(msgs),
        "updated_at": firestore.SERVER_TIMESTAMP,
    })
    return conv_id


# ---------------- 엔드포인트 ----------------
@router.post("", response_model=ConversationDetail, status_code=201, summary="대화 저장")
def save_conversation(body: ConversationCreate):
    try:
        conv_id = create_conversation([m.model_dump() for m in body.messages], body.title)
        return _to_item(get_db().collection(CONV_COLLECTION).document(conv_id).get(), with_messages=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"대화 저장 실패: {e}")


@router.get("", response_model=list[ConversationListItem], summary="대화 목록 조회 (messages 미포함)")
def list_conversations(limit: int = Query(50, ge=1, le=200, description="최대 개수 (최신 순)")):
    """목록에는 messages 를 넣지 않습니다. 대화 내용은 GET /api/conversations/{id} 로 불러옵니다."""
    try:
        docs = (get_db().collection(CONV_COLLECTION)
                .select(["title", "preview", "message_count", "created_at", "updated_at"])
                .order_by("updated_at", direction=firestore.Query.DESCENDING)
                .limit(limit).stream())
        return [_to_item(d) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"대화 목록 조회 실패: {e}")


@router.get("/{conv_id}", response_model=ConversationDetail, summary="대화 불러오기 (전체 messages)")
def get_conversation(conv_id: str):
    snap = get_db().collection(CONV_COLLECTION).document(conv_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail=f"대화를 찾을 수 없습니다: {conv_id}")
    return _to_item(snap, with_messages=True)


@router.delete("/{conv_id}", summary="대화 삭제")
def delete_conversation(conv_id: str):
    ref = get_db().collection(CONV_COLLECTION).document(conv_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail=f"대화를 찾을 수 없습니다: {conv_id}")
    try:
        ref.delete()
        return {"deleted": conv_id, "message": "대화가 삭제되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"대화 삭제 실패: {e}")