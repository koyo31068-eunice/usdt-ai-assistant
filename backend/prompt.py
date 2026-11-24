"""
시스템 프롬프트 만들기: 데이터 요약(/api/data/summary 결과)을 글로 바꿔 GPT에 주입
"""


def _won(v):
    return f"{v:,.0f}원" if isinstance(v, (int, float)) and float(v).is_integer() else f"{v:,.2f}원"


def build_system_prompt(s: dict) -> str:
    if not s or not s.get("count"):
        return ("당신은 빗썸 USDT/KRW 시장 데이터 분석 비서입니다. "
                "현재 저장된 데이터가 없으므로, 데이터가 필요한 질문에는 "
                "'저장된 데이터가 없습니다'라고 안내하세요. 한국어로 답하세요.")

    m = s["metrics"]
    lines = [
        "당신은 빗썸 USDT/KRW 시장 데이터 분석 비서입니다.",
        "",
        "[사용자 데이터 요약]",
        f"- 데이터: {s.get('unit', '')}",
        f"- 데이터 기간: {s['period']} (KST)",
        f"- 총 레코드: {s['count']}개",
        f"- 주요 지표: 평균 {_won(m['average'])}, 표준편차 {m['std']}원, "
        f"최고 {_won(m['max'])}({m['max_at']}), 최저 {_won(m['min'])}({m['min_at']})",
        f"- 기간 변화: {_won(m['first'])} → {_won(m['latest'])} ({m['change_pct']:+.2f}%), "
        f"마지막 데이터 시각 {m['latest_at']}",
        f"- 최근 트렌드: {s['trend']}",
    ]

    p = s.get("premium")
    if p:
        lines.append(f"- 환율 대비 괴리율(김치 프리미엄): 평균 {p['average_pct']:+.2f}%, "
                     f"최대 {p['max_pct']:+.2f}%, 최소 {p['min_pct']:+.2f}%, 최근 {p['latest_pct']:+.2f}%")

    sig = s.get("signals") or {}
    if sig:
        spikes = ", ".join(sig.get("volume_spike_times") or []) or "없음"
        lines.append(f"- 통합 신호 시간 수: Long {sig.get('Long', 0)}, Short {sig.get('Short', 0)}, "
                     f"Neutral {sig.get('Neutral', 0)} / 괴리 과열 {sig.get('premium_overheat_hours', 0)}시간")
        lines.append(f"- 거래량 급증 시각: {spikes}")

    if s.get("daily"):
        lines += ["", "[일별 요약] 날짜 | 시가 | 고가 | 저가 | 종가 | 변화율"]
        for d in s["daily"]:
            lines.append(f"- {d['day']} | {d['open']} | {d['high']} | {d['low']} | {d['close']} | "
                         f"{d['change_pct']:+.2f}%")

    if s.get("recent"):
        lines += ["", "[최근 12개 데이터] 시각 | 값 | 메모"]
        for r in s["recent"]:
            lines.append(f"- {r['date']} | {r['value']} | {r['memo']}")

    lines += [
        "",
        "[답변 규칙]",
        "1. 위 데이터에 근거해 한국어로 간결하게(3~6문장) 답하세요. 숫자는 원 단위와 시각을 함께 쓰세요.",
        "2. 데이터에 없는 내용(미래 가격, 다른 거래소, 뉴스 등)은 추측하지 말고 '저장된 데이터에는 없습니다'라고 말하세요.",
        "3. 메모의 '점수'는 기술적 지표 4종(MACD, Stoch RSI, Stochastic, BB %B)의 통합 점수이며 "
        "+2 이상 Long, -2 이하 Short, 그 사이는 Neutral입니다. 과거 분석에서 이 신호의 4시간 적중률은 약 58%였습니다.",
        "4. 매수·매도 판단을 물으면 데이터 근거를 설명하되, 투자 권유가 아닌 참고 정보임을 한 문장으로 덧붙이세요.",
    ]
    return "\n".join(lines)