"""LLM 기반 1차 파싱.

엔지니어마다 형식이 달라도, 붙여넣은 자유 텍스트를 LLM이
고정 스키마 JSON으로 정규화한다. 설정이 없거나 호출이 실패하면
호출 측(server)에서 규칙 기반 파서(parser.py)로 폴백한다.

환경변수:
    LLM_PROVIDER   "openai" | "bedrock" | "" (빈 값이면 LLM 비활성)
    # openai 호환 (사내 게이트웨이 / OpenAI 등)
    LLM_BASE_URL   예: http://localhost:8000/v1  (생략 시 OpenAI 기본)
    LLM_API_KEY    (또는 OPENAI_API_KEY)
    LLM_MODEL      예: gpt-4o-mini  (기본값)
    # bedrock
    BEDROCK_MODEL_ID  예: anthropic.claude-3-5-sonnet-20240620-v1:0
    AWS_REGION        예: us-east-1  (표준 자격증명 체인 사용)
"""

from __future__ import annotations

import json
import os
import re

from . import defaults

SCHEMA_HINT = """{
  "meta": {
    "eyebrow": "상단 소제목(영문 대문자 관례, 예: Infrastructure Notice)",
    "title": "문서 제목",
    "subtitle": "부제 (기간/요약)",
    "author": "작성자(원문에 없으면 빈 문자열로 두면 서버가 기본값 채움)",
    "written": "작성일 YYYY.MM.DD (알 수 없으면 빈 문자열)",
    "intro": "안내 문구 (없으면 빈 문자열)"
  },
  "eol_eos": [
    {
      "service": "서비스명(+버전)",
      "target": "대상 버전/항목 (없으면 빈 문자열)",
      "date": "종료·변경일 (원문 표기 유지)",
      "action": "전환 대상/조치/비고",
      "badge": "eol 또는 eos"
    }
  ],
  "whats_new": [
    {
      "title": "제목",
      "badge": "GA | PREVIEW | '' (없으면 빈 문자열)",
      "date": "출시일",
      "note": "제목 옆 부가설명 (예: 서울 리전 미출시, 없으면 '')",
      "body": "설명 본문",
      "url": "공식 URL (없으면 '')",
      "subitems": [
        {"subtitle": "하위 소제목", "badge": "", "date": "", "body": "", "url": ""}
      ]
    }
  ]
}"""

SYSTEM_PROMPT = f"""너는 AWS 서비스 변경사항 공지 텍스트를 구조화 JSON으로 변환하는 파서다.
입력은 엔지니어가 붙여넣은 자유 형식 텍스트(한국어/영어 혼용)이며 형식이 매번 다르다.

아래 스키마에 정확히 맞는 JSON만 출력한다. 설명, 마크다운, 코드펜스 없이 순수 JSON만.

스키마:
{SCHEMA_HINT}

규칙:
- EOL/EOS 섹션과 신규 출시(NEW) 섹션을 구분한다.
- eol_eos 의 service 와 target 을 반드시 분리한다:
  - service = 서비스 이름만 (버전 숫자 제외)
  - target  = 버전/대상 항목 (예: "3.05 / 3.06 / 3.07", "13", ".NET 8", "1.31 확장 지원")
  - 예: "Aurora MySQL 3.05 / 3.06" -> service="Aurora MySQL", target="3.05 / 3.06"
  - 예: "Lambda .NET 8" -> service="Lambda", target=".NET 8"
  - 예: "Amazon EKS - Kubernetes 1.31 확장 지원" -> service="Amazon EKS - Kubernetes", target="1.31 확장 지원"
  - 버전/대상이 없으면 target 은 빈 문자열.
- badge 판정 (하위 섹션 개념으로 일관되게 분류):
  - Sunset(운영 중 서비스 종료/EOL) → "eol"
  - Maintenance(신규 가입 중단, 기존 고객만 유지) → "eos"
  - SDK/도구 지원 종료(EOS), 요금 변경, 지표/방식 변경 → "eos"
- 'Sunset', 'EOL', 'Maintenance', 'SDK/도구' 같은 하위 섹션 헤더는 행이 아니다.
  그 아래 항목들에 공통 날짜/조치/배지를 적용한다.
- 서비스 그룹핑 규칙(일관성 유지):
  - 같은 종료일 + 같은 조치를 공유하고 개별 전환 대상이 없으면
    하나의 행으로 묶고 service 에 " · " 로 나열한다.
    (예: "FinSpace · Fraud Detector · Lookout for Equipment")
  - 서비스마다 전환 대상이나 날짜가 다르면 각각 별도 행으로 나눈다.
- 날짜는 YYYY.MM.DD 로 통일한다. 원문이 연-월까지만 있으면(YYYY.MM) 그대로 둔다.
  날짜/URL은 지어내지 않는다(없으면 빈 문자열).
- 내부 코멘트/고객사명/코드네임/내부 프로젝트명은 절대 포함하지 않는다.
  AWS 공식 발표 원문 기준으로만 요약한다.
- 한 항목에 여러 세부 항목(각각 URL/날짜)이 있으면 whats_new[].subitems 로 묶는다.
- whats_new 는 발표일(date) 최신순으로 정렬한다.
- badge(NEW)는 원문에 GA/PREVIEW가 명시된 경우에만 넣고, 없으면 빈 문자열(추측 금지).
- 섹션 순서는 항상 EOL/EOS → NEW 를 유지한다.
- 정보가 애매하면 비워두되, 항목 자체는 최대한 살린다.
- meta.title 이 원문에 없으면 "AWS 서비스 변경사항 안내" 를 사용한다.
- 반드시 유효한 JSON 하나만 출력한다."""


def provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "").strip().lower()


def available() -> bool:
    p = provider()
    if p == "openai":
        return bool(
            os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_BASE_URL")
        )
    if p == "bedrock":
        return bool(os.getenv("BEDROCK_MODEL_ID"))
    return False


def _extract_json(text: str) -> dict:
    """모델 출력에서 JSON 본문만 추출."""
    text = text.strip()
    # 코드펜스 제거
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 첫 { 부터 마지막 } 까지 시도
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e != -1 and e > s:
            return json.loads(text[s : e + 1])
        raise


def _call_openai(text: str) -> tuple[str, dict]:
    from openai import OpenAI

    client = OpenAI(
        base_url=os.getenv("LLM_BASE_URL") or None,
        api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "not-needed",
    )
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    u = getattr(resp, "usage", None)
    usage = {
        "input": getattr(u, "prompt_tokens", 0) if u else 0,
        "output": getattr(u, "completion_tokens", 0) if u else 0,
        "total": getattr(u, "total_tokens", 0) if u else 0,
        "model": model,
    }
    return (resp.choices[0].message.content or ""), usage


def _call_bedrock(text: str) -> tuple[str, dict]:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    model_id = os.getenv("BEDROCK_MODEL_ID")
    resp = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": text}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 4096},
    )
    parts = resp["output"]["message"]["content"]
    u = resp.get("usage", {})
    usage = {
        "input": u.get("inputTokens", 0),
        "output": u.get("outputTokens", 0),
        "total": u.get("totalTokens", 0),
        "model": model_id,
    }
    return "".join(p.get("text", "") for p in parts), usage


def normalize(data: dict) -> dict:
    """LLM 출력 스키마 보정."""
    data = data or {}
    meta = data.get("meta") or {}
    meta.setdefault("eyebrow", defaults.DEFAULT_EYEBROW)
    meta.setdefault("title", defaults.DEFAULT_TITLE)
    for k in ("subtitle", "author", "written", "intro"):
        meta.setdefault(k, "")
    if not meta.get("author"):
        meta["author"] = defaults.DEFAULT_AUTHOR

    eol = []
    for r in data.get("eol_eos") or []:
        badge = str(r.get("badge", "eol")).lower()
        # 하위 호환: 기존 "sunset" 값도 "eol"로 처리
        if badge == "sunset":
            badge = "eol"
        if badge not in ("eol", "eos"):
            badge = "eol"
        eol.append(
            {
                "service": r.get("service", ""),
                "target": r.get("target", ""),
                "date": r.get("date", ""),
                "action": r.get("action", ""),
                "badge": badge,
            }
        )

    new = []
    for r in data.get("whats_new") or []:
        subs = []
        for s in r.get("subitems") or []:
            subs.append(
                {
                    "subtitle": s.get("subtitle", ""),
                    "badge": (s.get("badge") or "").upper(),
                    "date": s.get("date", ""),
                    "body": s.get("body", ""),
                    "url": s.get("url", ""),
                }
            )
        new.append(
            {
                "title": r.get("title", ""),
                "badge": (r.get("badge") or "").upper(),
                "date": r.get("date", ""),
                "note": r.get("note", ""),
                "body": r.get("body", ""),
                "url": r.get("url", ""),
                "subitems": subs,
            }
        )

    return {"meta": meta, "eol_eos": eol, "whats_new": new}


def parse_with_llm(text: str) -> dict:
    """LLM으로 파싱. 실패 시 예외를 던진다(호출 측에서 폴백)."""
    p = provider()
    if p == "openai":
        raw, usage = _call_openai(text)
    elif p == "bedrock":
        raw, usage = _call_bedrock(text)
    else:
        raise RuntimeError("LLM provider not configured")
    data = normalize(_extract_json(raw))
    data["_usage"] = usage
    return data
