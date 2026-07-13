"""AWS 리포트 PDF 생성 웹앱 (FastAPI).

실행:
    .venv/bin/uvicorn webapp.server:app --host 0.0.0.0 --port 8000

엔드포인트:
    GET  /               편집 + 미리보기 페이지
    POST /api/parse      원본 스크립트 -> 구조화 데이터
    POST /api/preview    데이터 -> 미리보기 HTML
    POST /api/pdf        데이터 -> PDF 다운로드
"""

from __future__ import annotations

import datetime as _dt
import logging
from pathlib import Path
from urllib.parse import quote as _quote

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from . import llm_parser, renderer
from .parser import parse_script
from .summary import generate_summary
from .url_checker import check_urls

logger = logging.getLogger("aws_report_studio")

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSETS_DIR = ROOT / "assets"


def _load_dotenv() -> None:
    """프로젝트 루트의 .env 를 읽어 환경변수로 등록 (추가 의존성 없이)."""
    import os

    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        # 이미 환경에 있으면 덮어쓰지 않음(실제 환경변수 우선)
        os.environ.setdefault(key, val)


_load_dotenv()

app = FastAPI(title="AWS Report Studio")

# 내장 폰트를 미리보기 iframe에서 쓸 수 있도록 /assets 로 노출
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
# 프론트엔드 정적 파일(app.js 등)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/config")
def api_config() -> dict:
    """프론트가 LLM 사용 가능 여부를 표시하기 위한 정보."""
    import os

    provider = llm_parser.provider()
    model = ""
    if provider == "bedrock":
        model = os.getenv("BEDROCK_MODEL_ID", "")
    elif provider == "openai":
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    # 모델 ID에서 사람이 읽기 쉬운 이름만 추출 (예: claude-3-haiku)
    short = model
    if "claude" in model:
        import re as _re

        m = _re.search(r"claude[\w.\-]*?(haiku|sonnet|opus)[\w.\-]*", model)
        short = m.group(0) if m else model
    return {
        "llm_available": llm_parser.available(),
        "llm_provider": provider,
        "llm_model": model,
        "llm_model_short": short,
    }


def _consolidate_new(data: dict) -> dict:
    """신규 항목 설명을 일관되게 정리.

    설명은 항상 body 한 곳에 모아 제목 아래 한 줄로 심플하게 표시한다.
    note(짧은 리전/가용성 표기)가 있으면 body 앞에 자연스럽게 합친다.
    """
    for item in data.get("whats_new") or []:
        note = (item.get("note") or "").strip()
        body = (item.get("body") or "").strip()
        if note and body:
            item["body"] = f"{note}, {body}"
        elif note:
            item["body"] = note
        item["note"] = ""
    return data


@app.post("/api/parse")
def api_parse(payload: dict) -> dict:
    text = (payload or {}).get("text", "")
    # mode: "auto"(기본) | "llm" | "heuristic"
    mode = (payload or {}).get("mode", "auto")

    if mode != "heuristic" and llm_parser.available():
        try:
            data = llm_parser.parse_with_llm(text)
            data["_method"] = "llm"
            return _consolidate_new(data)
        except Exception as e:  # LLM 실패 시 규칙 파서로 폴백
            logger.warning("LLM 파싱 실패, 규칙 파서로 폴백합니다: %s", e, exc_info=True)
            data = parse_script(text)
            data["_method"] = "heuristic"
            data["_llm_error"] = str(e)[:200]
            return _consolidate_new(data)

    data = parse_script(text)
    data["_method"] = "heuristic"
    return _consolidate_new(data)


@app.post("/api/generate-summary")
def api_generate_summary(payload: dict) -> dict:
    """EOL/EOS + 신규 항목 데이터를 보고 두괄식 요약 HTML을 생성."""
    summary = generate_summary(payload or {})
    return {"summary": summary}


@app.post("/api/preview", response_class=HTMLResponse)
def api_preview(payload: dict) -> HTMLResponse:
    # check_urls=true 파라미터가 있을 때만 URL 체크 (미리보기 속도 우선)
    data = dict(payload or {})
    if data.pop("check_urls", False):
        data = check_urls(data)
    html = renderer.render_html(data, for_preview=True)
    return HTMLResponse(html)


@app.post("/api/check-urls")
def api_check_urls(payload: dict) -> dict:
    """URL 유효성 검사만 수행하고 결과를 반환 (프론트 진행 표시용)."""
    data = check_urls(dict(payload or {}))
    # 죽은 링크 요약만 추출해서 반환
    dead = []
    for item in data.get("whats_new") or []:
        s = item.get("url_status") or {}
        if s.get("dead"):
            dead.append(
                {"title": item.get("title", ""), "url": item.get("url", ""), "code": s.get("code")}
            )
        for sub in item.get("subitems") or []:
            s2 = sub.get("url_status") or {}
            if s2.get("dead"):
                dead.append(
                    {
                        "title": sub.get("subtitle", ""),
                        "url": sub.get("url", ""),
                        "code": s2.get("code"),
                    }
                )
    return {
        "data": data,
        "dead": dead,
        "total": len([i for i in (data.get("whats_new") or []) if i.get("url")]),
    }


@app.post("/api/pdf")
def api_pdf(payload: dict) -> Response:
    # PDF 생성 전 항상 URL 체크 (죽은 링크를 취소선으로 표시)
    data = check_urls(dict(payload or {}))
    html = renderer.render_html(data, for_preview=False)
    pdf_bytes = renderer.html_to_pdf_bytes(html)

    meta = (payload or {}).get("meta", {}) or {}
    stamp = _dt.date.today().strftime("%Y%m%d")
    base = (meta.get("title") or "aws-report").strip().replace(" ", "_")
    filename = f"{base}_{stamp}.pdf"
    # RFC 5987: 비ASCII 파일명은 퍼센트 인코딩, 헤더 전체는 latin-1 안전해야 함
    quoted = _quote(filename)
    disposition = f"attachment; filename=\"report_{stamp}.pdf\"; filename*=UTF-8''{quoted}"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
