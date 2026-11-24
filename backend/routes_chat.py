"""
AI 채팅 API
  POST /api/chat
  흐름: ① 데이터 요약 조회 → ② 시스템 프롬프트에 주입 → ③ GPT 호출 → ④ conversations 에 자동 저장
"""
from datetime import date

from fastapi import APIRouter, HTTPException
from openai import OpenAI

from config import (CHAT_DAILY_LIMIT, CHAT_HISTORY_LIMIT, OPENAI_API_KEY, OPENAI_MAX_TOKENS,
                    OPENAI_MODEL, OPENAI_REASONING_EFFORT)
from prompt import build_system_prompt
from routes_conversations import append_messages, create_conversation, get_conversation_messages
from routes_data import get_summary
from schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["AI 채팅"])

_client = None
_usage = {"day": None, "count": 0}         # 하루 요청 수 (과금 보호용, 서버 재시작 시 초기화)


def get_client():
    global _client
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY, timeout=60)
    return _client


def _check_daily_limit():
    today = date.today().isoformat()
    if _usage["day"] != today:
        _usage.update(day=today, count=0)
    if _usage["count"] >= CHAT_DAILY_LIMIT:
        raise HTTPException(status_code=429,
                            detail=f"오늘 채팅 한도({CHAT_DAILY_LIMIT}회)를 넘었습니다. 내일 다시 시도해 주세요.")
    _usage["count"] += 1


def _openai_error(e: Exception) -> HTTPException:
    """OpenAI 오류를 이해하기 쉬운 한글 메시지로 바꿈"""
    name = type(e).__name__
    msg = {
        "AuthenticationError": "OpenAI API 키가 올바르지 않습니다. OPENAI_API_KEY 를 확인하세요.",
        "RateLimitError": "OpenAI 사용 한도 초과 또는 크레딧 부족입니다. 결제/사용량 설정을 확인하세요.",
        "NotFoundError": f"모델 '{OPENAI_MODEL}' 을(를) 사용할 수 없습니다. OPENAI_MODEL 값을 확인하세요.",
        "PermissionDeniedError": f"이 계정은 모델 '{OPENAI_MODEL}' 사용 권한이 없습니다.",
        "BadRequestError": f"OpenAI 요청 형식 오류입니다 (모델: {OPENAI_MODEL}).",
        "APIConnectionError": "OpenAI 서버에 연결하지 못했습니다. 잠시 후 다시 시도하세요.",
        "APITimeoutError": "OpenAI 응답 시간이 초과되었습니다. 잠시 후 다시 시도하세요.",
    }.get(name, "AI 답변 생성 중 오류가 발생했습니다.")
    code = 429 if name == "RateLimitError" else 502
    return HTTPException(status_code=code, detail=f"{msg} ({name}: {str(e)[:200]})")


@router.post("/chat", response_model=ChatResponse, summary="AI 채팅 (데이터 요약 주입 + 자동 저장)")
def chat(body: ChatRequest):
    client = get_client()
    _check_daily_limit()

    # ① 데이터 요약 조회 (5분 캐시)
    try:
        summary = get_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터 요약 조회 실패: {e}")

    # ② 시스템 프롬프트 + 이전 대화(최근 N개) + 이번 질문
    history = []
    if body.conversation_id:
        old = get_conversation_messages(body.conversation_id)        # 없으면 404
        history = [{"role": m["role"], "content": m["content"]} for m in old][-CHAT_HISTORY_LIMIT:]
    messages = ([{"role": "system", "content": build_system_prompt(summary)}]
                + history
                + [{"role": "user", "content": body.message}])

    # ③ GPT 호출
    params = {"model": OPENAI_MODEL, "messages": messages, "max_completion_tokens": OPENAI_MAX_TOKENS}
    if OPENAI_REASONING_EFFORT:
        params["reasoning_effort"] = OPENAI_REASONING_EFFORT
    try:
        res = client.chat.completions.create(**params)
    except Exception as e:
        raise _openai_error(e)

    reply = (res.choices[0].message.content or "").strip()
    if not reply:
        raise HTTPException(status_code=502,
                            detail="AI 답변이 비어 있습니다. OPENAI_MAX_TOKENS 를 늘리거나 다른 모델을 사용해 보세요.")

    # ④ 대화 자동 저장
    pair = [{"role": "user", "content": body.message}, {"role": "assistant", "content": reply}]
    try:
        if body.conversation_id:
            conv_id = append_messages(body.conversation_id, pair)
        else:
            conv_id = create_conversation(pair)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"답변은 생성됐지만 대화 저장에 실패했습니다: {e}")

    usage = None
    if getattr(res, "usage", None):
        usage = {"prompt_tokens": res.usage.prompt_tokens,
                 "completion_tokens": res.usage.completion_tokens,
                 "total_tokens": res.usage.total_tokens}

    return {
        "conversation_id": conv_id,
        "reply": reply,
        "model": getattr(res, "model", OPENAI_MODEL),
        "summary_used": {"period": summary.get("period"), "count": summary.get("count"),
                         "trend": summary.get("trend")},
        "usage": usage,
    }