"""두괄식 요약 생성 모듈.

EOL/EOS + 신규 출시 데이터를 바탕으로 "이번 달 핵심 내용"을
두괄식으로 요약한 HTML 문자열을 반환한다.

LLM 연결 시: Bedrock/OpenAI로 자연스러운 문장 생성
LLM 없을 시: 규칙 기반으로 항목명을 조합해 생성 (fallback)

반환 형식: <strong>강조</strong> 태그가 포함된 HTML 인라인 문자열
(템플릿에서 | safe 필터로 렌더링)
"""

from __future__ import annotations

import logging

from . import llm_parser

logger = logging.getLogger("aws_report_studio")

_SUMMARY_SYSTEM = """너는 AWS 엔지니어링 뉴스레터 편집자다.
주어진 JSON 데이터(EOL/EOS 종료 항목 + 신규 출시 항목)를 읽고,
고객이 이번 달에 가장 집중해야 할 핵심 내용을 **두괄식으로 2~3문장**으로 요약해라.

규칙:
- 일반 고객(엔지니어)이 바로 이해할 수 있는 평문으로 작성.
- 강조할 서비스명, 날짜, 숫자는 <strong>태그</strong>로 감싼다.
- 전체 항목을 나열하지 말고, 가장 임팩트 있는 3~4개만 언급.
- EOL/EOS 중 일반적으로 많이 쓰는 서비스(Aurora, EKS, Lambda, RDS 등) 위주로 선별.
- 신규 출시 중 주목할 만한 GA 항목 1~2개 포함.
- 문장 끝 마침표 포함. 마크다운 금지. HTML 태그는 <strong>만 사용.
- 한국어로 작성. 반드시 HTML 문자열 하나만 출력(설명 없이).

예시 출력:
이번 달은 <strong>DB 버전 및 쿠버네티스 EOL 일정</strong>이 집중되어 있습니다. <strong>Aurora MySQL 3.05~3.07</strong>, <strong>EKS 1.31/1.34</strong>, <strong>Lambda .NET 8</strong> 등 운영 중인 서비스 버전 확인이 필요합니다. 신규 기능 중에는 <strong>Bedrock OpenAI 모델 GA</strong>와 <strong>Aurora PostgreSQL 18</strong> 지원이 주목할 만합니다."""


def _rule_based_summary(data: dict) -> str:
    """LLM 없을 때 규칙 기반으로 요약 생성."""
    eol_items = data.get("eol_eos") or []
    new_items = data.get("whats_new") or []

    # EOL 항목 중 일반 서비스 우선 (Aurora, EKS, Lambda, RDS, MSK 등)
    priority_keywords = [
        "aurora",
        "eks",
        "lambda",
        "rds",
        "msk",
        "kafka",
        "elasticache",
        "opensearch",
    ]
    eol_priority = [
        i
        for i in eol_items
        if any(kw in (i.get("service") or "").lower() for kw in priority_keywords)
    ]
    eol_others = [i for i in eol_items if i not in eol_priority]
    eol_featured = (eol_priority + eol_others)[:4]

    # 신규 항목 중 GA 배지 우선
    new_ga = [i for i in new_items if (i.get("badge") or "").upper() == "GA"]
    new_featured = (new_ga + [i for i in new_items if i not in new_ga])[:2]

    parts = []

    if eol_featured:
        names = ", ".join(
            f"<strong>{i['service']}{(' ' + i['target']) if i.get('target') else ''}</strong>"
            for i in eol_featured[:3]
        )
        suffix = f" 외 {len(eol_items) - 3}건" if len(eol_items) > 3 else ""
        parts.append(
            f"이번 달은 {names}{suffix} 등 <strong>서비스 종료 · 변경 일정</strong>이 있습니다."
        )

    if new_featured:
        names = ", ".join(
            f"<strong>{i['title']}{(' ' + i['badge']) if i.get('badge') else ''}</strong>"
            for i in new_featured
        )
        parts.append(f"신규 출시 중에는 {names} 가 주목할 만합니다.")

    return " ".join(parts) if parts else ""


def _llm_summary(data: dict) -> str:
    """LLM으로 두괄식 요약 생성."""
    import json

    # 핵심 데이터만 전달 (토큰 절약)
    slim = {
        "eol_eos": [
            {
                "service": i.get("service"),
                "target": i.get("target"),
                "date": i.get("date"),
                "badge": i.get("badge"),
            }
            for i in (data.get("eol_eos") or [])
        ],
        "whats_new": [
            {
                "title": i.get("title"),
                "badge": i.get("badge"),
                "date": i.get("date"),
                "body": (i.get("body") or "")[:80],
            }
            for i in (data.get("whats_new") or [])
        ],
    }

    provider = llm_parser.provider()
    if provider == "openai":
        import os

        from openai import OpenAI

        client = OpenAI(
            base_url=os.getenv("LLM_BASE_URL") or None,
            api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "not-needed",
        )
        resp = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=0.3,
            messages=[
                {"role": "system", "content": _SUMMARY_SYSTEM},
                {"role": "user", "content": json.dumps(slim, ensure_ascii=False)},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    elif provider == "bedrock":
        import os

        import boto3

        client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
        resp = client.converse(
            modelId=os.getenv("BEDROCK_MODEL_ID"),
            system=[{"text": _SUMMARY_SYSTEM}],
            messages=[
                {"role": "user", "content": [{"text": json.dumps(slim, ensure_ascii=False)}]}
            ],
            inferenceConfig={"temperature": 0.3, "maxTokens": 512},
        )
        parts = resp["output"]["message"]["content"]
        return "".join(p.get("text", "") for p in parts).strip()

    raise RuntimeError("LLM provider not configured")


def generate_summary(data: dict) -> str:
    """두괄식 요약 HTML 반환. LLM 실패 시 규칙 기반으로 폴백."""
    if llm_parser.available():
        try:
            return _llm_summary(data)
        except Exception as e:
            logger.warning("요약 LLM 실패, 규칙 기반으로 폴백: %s", e)

    return _rule_based_summary(data)
