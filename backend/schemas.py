"""
요청/응답 데이터 형식 + 입력값 검증 (Pydantic)
잘못된 값이 들어오면 FastAPI가 자동으로 422 오류와 이유를 돌려줍니다.
"""
from datetime import datetime
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

DATE_FORMATS = ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")


def normalize_date(v: str) -> str:
    """여러 날짜 형식을 받아서 'YYYY-MM-DDTHH:MM' 하나로 통일"""
    v = (v or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            continue
    raise ValueError("date 형식은 YYYY-MM-DDTHH:MM 이어야 합니다 (예: 2026-11-11T00:00)")


# ---------------- data ----------------
class DataCreate(BaseModel):
    date: str = Field(..., description="시각 (KST) YYYY-MM-DDTHH:MM", examples=["2026-11-11T00:00"])
    value: float = Field(..., gt=0, lt=100000, description="USDT/KRW 가격(원), 0보다 커야 함", examples=[1357])
    memo: str = Field("", max_length=200, description="메모 (최대 200자)", examples=["테스트로 추가한 데이터"])

    @field_validator("date")
    @classmethod
    def _date(cls, v):
        return normalize_date(v)

    @field_validator("memo")
    @classmethod
    def _memo(cls, v):
        return (v or "").strip()


class DataUpdate(BaseModel):
    """수정할 항목만 보내면 됩니다 (최소 1개)"""
    date: Optional[str] = Field(None, examples=["2026-11-11T00:00"])
    value: Optional[float] = Field(None, gt=0, lt=100000, examples=[1360])
    memo: Optional[str] = Field(None, max_length=200, examples=["값 수정 테스트"])

    @field_validator("date")
    @classmethod
    def _date(cls, v):
        return None if v is None else normalize_date(v)

    @field_validator("memo")
    @classmethod
    def _memo(cls, v):
        return None if v is None else v.strip()

    @model_validator(mode="after")
    def _at_least_one(self):
        if self.date is None and self.value is None and self.memo is None:
            raise ValueError("date, value, memo 중 최소 1개는 보내야 합니다")
        return self


class DataOut(BaseModel):
    id: str
    date: str
    value: Union[int, float]
    memo: str = ""
    source: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None



# ---------------- conversations ----------------
class Message(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="user(사용자) 또는 assistant(AI)")
    content: str = Field(..., min_length=1, max_length=4000, description="메시지 내용 (최대 4000자)")
    created_at: Optional[str] = Field(None, description="비워 두면 서버가 현재 시각을 넣음")

    @field_validator("content")
    @classmethod
    def _content(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("content 는 비어 있을 수 없습니다")
        return v


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=100, description="비워 두면 첫 질문으로 자동 생성",
                                 examples=["최근 USDT 흐름 질문"])
    messages: list[Message] = Field(..., min_length=1, max_length=200,
                                    examples=[[{"role": "user", "content": "최근 USDT 흐름 어때?"},
                                               {"role": "assistant", "content": "최근 24시간은 소폭 하락했어요."}]])


class ConversationListItem(BaseModel):
    """목록 조회용 - messages 는 포함하지 않음 (불러오기는 GET /api/conversations/{id})"""
    id: str
    title: str
    preview: str = ""
    message_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConversationDetail(ConversationListItem):
    messages: list[Message] = []



# ---------------- chat ----------------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="사용자 질문 (최대 1000자)",
                         examples=["최근 USDT 흐름 어때?"])
    conversation_id: Optional[str] = Field(None, description="이어서 대화할 대화 id (비우면 새 대화)")

    @field_validator("message")
    @classmethod
    def _message(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("message 는 비어 있을 수 없습니다")
        return v


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    model: str
    summary_used: dict
    usage: Optional[dict] = None

class ConversationDetail(ConversationListItem):
    messages: list[Message] = []

    

# ---------------- chat ----------------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="사용자 질문 (최대 1000자)",
                         examples=["최근 USDT 흐름 어때?"])
    conversation_id: Optional[str] = Field(None, description="이어서 대화할 대화 id (비우면 새 대화)")

    @field_validator("message")
    @classmethod
    def _message(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("message 는 비어 있을 수 없습니다")
        return v


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    model: str
    summary_used: dict
    usage: Optional[dict] = None