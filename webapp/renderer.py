"""데이터 -> HTML -> PDF 렌더링 공용 모듈.

generate.py(CLI)와 server.py(웹) 양쪽에서 동일하게 사용하여
미리보기와 PDF 결과가 항상 일치하도록 보장한다.
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "templates"
TEMPLATE_NAME = "report.html.j2"
LOGO_PATH = ROOT / "assets" / "logo.png"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _logo_data_uri() -> str:
    """로고를 base64 data URI로 반환. 파일이 없으면 빈 문자열."""
    if not LOGO_PATH.exists():
        return ""
    data = base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return f"data:image/png;base64,{data}"


def normalize(data: dict) -> dict:
    """필수 키 보정."""
    data = dict(data or {})
    data.setdefault("meta", {})
    data.setdefault("eol_eos", [])
    data.setdefault("whats_new", [])
    return data


def render_html(data: dict, *, for_preview: bool = False) -> str:
    """데이터로 HTML 문자열 생성.

    for_preview=True 이면 폰트/로고 경로를 브라우저에서 접근 가능한
    절대 URL(/assets/...)로 만들어 웹 미리보기에서도 보이게 한다.
    PDF(for_preview=False)에는 base64 data URI로 로고를 임베드한다.
    """
    data = normalize(data)
    template = _env.get_template(TEMPLATE_NAME)

    if for_preview:
        logo_src = "/assets/logo.png"
    else:
        logo_src = _logo_data_uri()

    html = template.render(**data, logo_src=logo_src)

    if for_preview:
        html = html.replace('url("assets/fonts/', 'url("/assets/fonts/')
    return html


def html_to_pdf_bytes(html: str) -> bytes:
    """HTML 문자열을 PDF 바이트로 변환 (Playwright/Chromium)."""
    from playwright.sync_api import sync_playwright

    # 내장 폰트(assets/fonts) 상대경로 해석을 위해 프로젝트 루트에 임시 HTML 작성
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", dir=str(ROOT), encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(html)
        tmp_path = Path(tmp.name)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(tmp_path.as_uri(), wait_until="networkidle")
            page.emulate_media(media="print")
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "16mm", "bottom": "16mm", "left": "15mm", "right": "15mm"},
                prefer_css_page_size=True,
            )
            browser.close()
        return pdf_bytes
    finally:
        tmp_path.unlink(missing_ok=True)
