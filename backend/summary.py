"""
데이터 요약 계산 (AI 시스템 프롬프트에 넣을 '요약 정보')
- 입력: [{date, value, memo}, ...]  (date 오름차순)
- 출력: 기간, 개수, 기본 통계, 최근 추세, 일별 요약, 신호 집계, 최근 12개 값
"""
import re
from statistics import mean, pstdev

PREMIUM_RE = re.compile(r"괴리\s*([+-]?\d+(?:\.\d+)?)%")


def _fmt_dt(s):
    """'2026-11-01T00:00' → '2026-11-01 00:00'"""
    return s.replace("T", " ")


def _pct(a, b):
    return round((b / a - 1) * 100, 2) if a else 0.0


def _trend(values):
    """최근 24개 평균 vs 직전 24개 평균 (데이터가 적으면 절반씩 비교)"""
    n = 24 if len(values) >= 48 else max(1, len(values) // 2)
    recent, prev = values[-n:], values[-2 * n:-n]
    if not prev:
        return "판단 불가 (데이터 부족)", {}
    change = _pct(mean(prev), mean(recent))
    if change > 0.1:
        label = "상승"
    elif change < -0.1:
        label = "하락"
    else:
        label = "유지(보합)"
    detail = {
        "window": f"최근 {n}개 평균 vs 직전 {n}개 평균",
        "recent_avg": round(mean(recent), 2),
        "prev_avg": round(mean(prev), 2),
        "change_pct": change,
        "last_n_change_pct": _pct(values[-n - 1] if len(values) > n else values[0], values[-1]),
    }
    return f"{label} (최근 {n}시간 평균이 직전 {n}시간 대비 {change:+.2f}%)", detail


def compute_summary(rows):
    if not rows:
        return {"period": "-", "count": 0, "metrics": {}, "trend": "데이터 없음",
                "message": "저장된 데이터가 없습니다."}

    values = [r["value"] for r in rows]
    i_max = max(range(len(values)), key=values.__getitem__)
    i_min = min(range(len(values)), key=values.__getitem__)
    trend, trend_detail = _trend(values)

    # 일별 요약 (최근 31일)
    daily = {}
    for r in rows:
        day = r["date"][:10]
        d = daily.setdefault(day, {"day": day, "open": r["value"], "high": r["value"],
                                   "low": r["value"], "close": r["value"], "count": 0})
        d["high"] = max(d["high"], r["value"])
        d["low"] = min(d["low"], r["value"])
        d["close"] = r["value"]
        d["count"] += 1
    daily_list = list(daily.values())[-31:]
    for d in daily_list:
        d["change_pct"] = _pct(d["open"], d["close"])

    # memo 에 담긴 분석 신호 집계
    memos = [r.get("memo") or "" for r in rows]
    premiums = [float(m.group(1)) for m in map(PREMIUM_RE.search, memos) if m]
    signals = {
        "Long": sum("Long" in m for m in memos),
        "Short": sum("Short" in m for m in memos),
        "Neutral": sum("Neutral" in m for m in memos),
        "volume_spike_times": [_fmt_dt(r["date"]) for r, m in zip(rows, memos) if "거래량급증" in m][:10],
        "premium_overheat_hours": sum("괴리과열" in m for m in memos),
    }
    premium = None
    if premiums:
        premium = {"average_pct": round(mean(premiums), 2), "max_pct": max(premiums),
                   "min_pct": min(premiums), "latest_pct": premiums[-1]}

    return {
        "period": f"{_fmt_dt(rows[0]['date'])} ~ {_fmt_dt(rows[-1]['date'])}",
        "count": len(rows),
        "unit": "KRW per USDT (빗썸 USDT/KRW 1시간봉 종가)",
        "metrics": {
            "average": round(mean(values), 2),
            "std": round(pstdev(values), 2),
            "max": values[i_max], "max_at": _fmt_dt(rows[i_max]["date"]),
            "min": values[i_min], "min_at": _fmt_dt(rows[i_min]["date"]),
            "first": values[0], "latest": values[-1], "latest_at": _fmt_dt(rows[-1]["date"]),
            "change_pct": _pct(values[0], values[-1]),
        },
        "trend": trend,
        "trend_detail": trend_detail,
        "premium": premium,
        "signals": signals,
        "daily": daily_list,
        "recent": [{"date": _fmt_dt(r["date"]), "value": r["value"], "memo": r.get("memo") or ""}
                   for r in rows[-12:]],
    }