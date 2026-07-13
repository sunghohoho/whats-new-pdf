"""원본 스크립트(자유 텍스트) -> 구조화 데이터(best-effort).

AWS 공지 텍스트는 형식이 다양하다. 다음 패턴을 폭넓게 지원한다.

EOL/EOS 예:
    AWS WAF Classic — 2026.10.07 종료 → WAFv2
    AWS Proton — 2026.10.07 종료 (신규 가입 이미 중단)
    Aurora MySQL 3.05 / 3.06 — (2026.06.30) → 3.10 이상으로 자동 업그레이드
    App Runner · Audit Manager · ...            (섹션 헤더의 공통 날짜/조치 적용)

하위 섹션 헤더(Sunset / Maintenance / SDK)는 행이 아니라
아래 항목들에 적용될 공통 배지·날짜·조치로 처리한다.

NEW 예:
    Claude Opus 4.8 on AWS (2026.05.28)
    Amazon OpenSearch Serverless (GA, 2026.05.28)

완벽을 보장하지 않는다. 최대한 채워주고 나머지는 웹 폼에서 보정한다.
"""

from __future__ import annotations

import re

from . import defaults

# 날짜: 2026.10.07 / 2026-05-20 / 2026.05 / 2026.04.30
_DATE = re.compile(r"\d{4}[.\-]\d{1,2}(?:[.\-]\d{1,2})?")
_URL = re.compile(r"https?://\S+")
_DASH = re.compile(r"[—–―]")

_SEC_EOL = re.compile(r"eol\s*/?\s*eos|서비스\s*종료|종료\s*예정", re.I)
_SEC_NEW = re.compile(r"^\s*(new|신규)\b", re.I)

# 하위 섹션 헤더 -> (배지, 기본 조치)
_SUBHEADERS = [
    (re.compile(r"^\s*sunset\b", re.I), "eol", ""),
    (re.compile(r"^\s*maintenance\b", re.I), "eos", "신규 가입 차단"),
    (re.compile(r"^\s*(sdk|개발\s*도구|도구)\b", re.I), "eos", ""),
]

_BADGE_TOK = re.compile(r"\b(GA|PREVIEW|Preview|GENERALLY AVAILABLE)\b", re.I)


def _clean(s: str) -> str:
    # 양끝의 공백/구분자만 제거 (괄호는 본문의 일부일 수 있어 남긴다)
    return s.strip().strip("·•-—–―,. ").strip()


def _extract_date(text: str) -> str:
    m = _DATE.search(text)
    return m.group(0) if m else ""


# 서비스명 끝에 붙은 버전/대상(예: "3.05 / 3.06", "13", ".NET 8", "1.31 확장 지원")
_VER_TAIL = re.compile(
    r"\s+((?:\.NET\s+)?\d[\w.]*(?:\s*/\s*[\w.]+)*(?:\s+(?:확장|표준)\s*지원(?:\s*EOL)?)?)\s*$"
)


def _split_target(service: str) -> tuple[str, str]:
    """'Aurora MySQL 3.05 / 3.06' -> ('Aurora MySQL', '3.05 / 3.06')."""
    m = _VER_TAIL.search(service)
    if m:
        name = service[: m.start()].strip()
        if name:  # 이름이 통째로 버전으로 빨려가지 않도록
            return name, m.group(1).strip()
    return service, ""


def _detect_subheader(line: str):
    for rx, badge, action in _SUBHEADERS:
        if rx.match(line):
            return badge, action, _extract_date(line)
    return None


def _parse_eol_row(line: str, ctx_badge: str, ctx_action: str, ctx_date: str) -> dict | None:
    raw = _DASH.sub("—", line).strip()
    if not raw:
        return None

    # 명시적 구분 마커 {eol} | {eos} (표준 형식, 하위 호환: {sunset}도 eol로 처리)
    explicit_badge = None
    mb = re.search(r"\{\s*(sunset|eol|eos)\s*\}", raw, re.I)
    if mb:
        raw_badge = mb.group(1).lower()
        explicit_badge = "eol" if raw_badge == "sunset" else raw_badge
        raw = (raw[: mb.start()] + raw[mb.end() :]).strip()

    # 서비스 / 상세 분리 (em대시 우선)
    if "—" in raw:
        service, rest = raw.split("—", 1)
    else:
        # 대시가 없으면 날짜 앞까지를 서비스로, 없으면 전체를 서비스로
        m = _DATE.search(raw)
        if m:
            service, rest = raw[: m.start()], raw[m.start() :]
        else:
            service, rest = raw, ""

    service = _clean(service)
    if not service:
        return None

    # 서비스명 끝의 버전/대상을 target 으로 분리
    service, target = _split_target(service)

    # 날짜
    date = _extract_date(rest) or _extract_date(raw) or ctx_date

    # 조치/전환 대상
    action = ""
    if "→" in rest:
        action = _clean(rest.split("→", 1)[1])
    else:
        # 날짜 제거 후 남는 설명(종료/EOS/신규 가입 차단 등)
        tail = _DATE.sub("", rest)
        tail = re.sub(r"\b(부|까지|기준)\b", "", tail)
        action = _clean(tail)
    if not action:
        action = ctx_action

    # 배지: {마커} 최우선, 그다음 명시적 신호, 없으면 섹션 컨텍스트
    low = raw.lower()
    if explicit_badge:
        badge = explicit_badge
    elif "eos" in low:
        badge = "eos"
    elif "신규 가입" in raw or "중단" in raw:
        badge = "eos"
    elif "종료" in raw:
        badge = ctx_badge or "eol"
    else:
        badge = ctx_badge or "eol"

    return {"service": service, "target": target, "date": date, "action": action, "badge": badge}


def _parse_new_block(lines: list[str]) -> dict | None:
    text_lines = [ln.strip() for ln in lines if ln.strip()]
    if not text_lines:
        return None

    url = ""
    title = ""
    body_lines: list[str] = []
    for ln in text_lines:
        m = _URL.search(ln)
        if m:
            url = m.group(0)
            continue
        if not title:
            title = ln
        else:
            body_lines.append(ln)

    if not title:
        return None

    badge = ""
    date = ""

    # 제목 끝의 괄호 그룹 파싱: (GA, 2026.05.28) / (2026.05.28) / (GA, 2026.05)
    mparen = re.search(r"\(([^)]*)\)\s*$", title)
    if mparen:
        inside = mparen.group(1)
        bm = _BADGE_TOK.search(inside)
        if bm:
            badge = bm.group(1).upper()
            if badge == "GENERALLY AVAILABLE":
                badge = "GA"
        d = _extract_date(inside)
        if d:
            date = d
        # 괄호가 배지/날짜 용도였다면 제목에서 제거
        if bm or d:
            title = title[: mparen.start()].strip()

    # 제목 끝의 단독 GA/PREVIEW (괄호 없이)
    if not badge:
        bm2 = re.search(r"\b(GA|PREVIEW)\b\s*$", title)
        if bm2:
            badge = bm2.group(1).upper()
            title = title[: bm2.start()].strip()

    body = " ".join(body_lines).strip()

    # 날짜가 아직 없으면 제목/본문에서 탐색
    if not date:
        date = _extract_date(title) or _extract_date(body)

    # 제목이 "제목 ... (2026.06.17) 설명" 처럼 한 줄인 경우 분리
    if not body:
        m = _DATE.search(title)
        if m:
            head = _clean(title[: m.start()])
            tail = title[m.end() :].strip(" ,.·-—–―()")
            if tail:
                title, body = head, tail

    # 제목/본문에서 잔여 날짜 괄호 제거
    title = re.sub(r"\(\s*" + _DATE.pattern + r"\s*\)", "", title).strip(" ,.")
    title = _clean(title) if title else title
    body = re.sub(r"\(\s*" + _DATE.pattern + r"\s*\)", "", body).strip(" ,.")

    return {
        "title": title,
        "badge": badge,
        "date": date,
        "note": "",
        "body": body,
        "url": url,
        "subitems": [],
    }


def parse_script(text: str) -> dict:
    lines = text.replace("\r\n", "\n").split("\n")

    # 섹션 경계
    eol_start, new_start = None, None
    for i, ln in enumerate(lines):
        if eol_start is None and _SEC_EOL.search(ln):
            eol_start = i
        if _SEC_NEW.match(ln):
            new_start = i
            break
    if eol_start is None:
        eol_start = 0

    eol_lines = lines[eol_start + 1 : new_start] if new_start else lines[eol_start + 1 :]
    new_lines = lines[new_start + 1 :] if new_start else []

    # ── EOL/EOS (하위 섹션 컨텍스트 유지) ──
    eol_eos = []
    ctx_badge, ctx_action, ctx_date = "eol", "", ""
    for ln in eol_lines:
        if not ln.strip():
            continue
        sub = _detect_subheader(ln)
        if sub:
            ctx_badge, ctx_action, ctx_date = sub[0], sub[1], sub[2]
            continue
        row = _parse_eol_row(ln, ctx_badge, ctx_action, ctx_date)
        if row:
            eol_eos.append(row)

    # ── NEW (URL을 블록 경계로) ──
    whats_new = []
    block: list[str] = []
    for ln in new_lines:
        block.append(ln)
        if _URL.search(ln):
            item = _parse_new_block(block)
            if item:
                whats_new.append(item)
            block = []
    if block:
        item = _parse_new_block(block)
        if item:
            whats_new.append(item)

    return {
        "meta": {
            "eyebrow": defaults.DEFAULT_EYEBROW,
            "title": defaults.DEFAULT_TITLE,
            "subtitle": "",
            "author": defaults.DEFAULT_AUTHOR,
            "written": "",
            "intro": "",
        },
        "eol_eos": eol_eos,
        "whats_new": whats_new,
    }
