"""
STEP 3. USDT/KRW 분석 결과를 Firestore 'data' 컬렉션에 업로드
- 입력: backend/data/features_1h.csv  (지난 프로젝트 결과, 분석 기간 240건만 사용)
- 저장 형식: { date, value, memo, source, created_at, updated_at }
    date  : "2026-11-01T00:00"  (KST, 1시간봉 시각)
    value : USDT/KRW 종가 (원)
    memo  : "괴리 +0.47% · 점수 +2 · Long · 거래량급증"

실행 (backend 폴더에서)
    python scripts/seed_data.py --dry-run   # 미리보기만 (DB에 쓰지 않음)
    python scripts/seed_data.py             # 업로드
    python scripts/seed_data.py --reset     # data 컬렉션을 비우고 다시 업로드
"""
import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))          # backend 폴더의 config.py, db.py 를 불러오기 위해

CSV_PATH = BACKEND_DIR / "data" / "features_1h.csv"


def to_bool(v):
    return str(v).strip().lower() == "true"


def make_memo(row):
    """한 시간봉의 분석 결과를 짧은 메모로 요약"""
    parts = []
    try:
        parts.append(f"괴리 {float(row['premium_pct']):+.2f}%")
    except (KeyError, ValueError):
        pass
    try:
        parts.append(f"점수 {int(float(row['score'])):+d}")
    except (KeyError, ValueError):
        pass
    if row.get("decision"):
        parts.append(row["decision"])
    if to_bool(row.get("vol_anom")):
        parts.append("거래량급증")
    if row.get("premium_state") == "과열":
        parts.append("괴리과열")
    return " · ".join(parts)


def load_rows():
    if not CSV_PATH.exists():
        sys.exit(f"[오류] 파일이 없습니다: {CSV_PATH}")

    rows = []
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if not to_bool(r.get("is_analysis")):       # 준비 구간(10/25~10/31)은 제외
                continue
            dt = datetime.fromisoformat(r["datetime"])   # 2026-11-01 00:00:00+09:00
            close = float(r["close"])
            rows.append({
                "doc_id": dt.strftime("seed_%Y%m%d_%H00"),   # 같은 시각은 같은 ID → 다시 실행해도 중복 없음
                "date": dt.strftime("%Y-%m-%dT%H:%M"),
                "value": int(close) if close.is_integer() else round(close, 2),
                "memo": make_memo(r),
            })
    return rows


def reset_collection(db, name):
    deleted = 0
    while True:
        docs = db.collection(name).limit(400).get()
        if not docs:
            break
        batch = db.batch()
        for d in docs:
            batch.delete(d.reference)
        batch.commit()
        deleted += len(docs)
    return deleted


def upload(db, name, rows):
    from firebase_admin import firestore

    for i in range(0, len(rows), 400):                    # 배치 1회 최대 500건 → 400건씩
        batch = db.batch()
        for r in rows[i:i + 400]:
            ref = db.collection(name).document(r["doc_id"])
            batch.set(ref, {
                "date": r["date"],
                "value": r["value"],
                "memo": r["memo"],
                "source": "seed",
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
        batch.commit()
        print(f"  업로드 {min(i + 400, len(rows))} / {len(rows)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 미리보기만")
    ap.add_argument("--reset", action="store_true", help="업로드 전에 data 컬렉션 비우기")
    args = ap.parse_args()

    rows = load_rows()
    values = [r["value"] for r in rows]
    print("========== 업로드 대상 ==========")
    print(f"파일   : {CSV_PATH.name}")
    print(f"건수   : {len(rows)}건")
    print(f"기간   : {rows[0]['date']} ~ {rows[-1]['date']}")
    print(f"값 범위: {min(values):,} ~ {max(values):,}원 (평균 {sum(values) / len(values):,.1f})")
    print("\n[앞 3건 미리보기]")
    for r in rows[:3]:
        print(f"  {r['date']} | {r['value']:>6} | {r['memo']}")
    print("[거래량급증 메모 예시]")
    for r in [x for x in rows if "거래량급증" in x["memo"]][:3]:
        print(f"  {r['date']} | {r['value']:>6} | {r['memo']}")

    if args.dry_run:
        print("\n(--dry-run) 미리보기만 했습니다. DB에는 쓰지 않았습니다.")
        sys.exit(0)

    from config import DATA_COLLECTION
    from db import get_db

    db = get_db()
    if args.reset:
        print(f"\n'{DATA_COLLECTION}' 컬렉션 비우는 중...")
        print(f"  삭제 {reset_collection(db, DATA_COLLECTION)}건")

    print(f"\n'{DATA_COLLECTION}' 컬렉션에 업로드 중...")
    upload(db, DATA_COLLECTION, rows)

    total = len(db.collection(DATA_COLLECTION).get())
    print(f"\n✅ 완료: 현재 '{DATA_COLLECTION}' 컬렉션 문서 수 = {total}건")