#!/usr/bin/env python3
"""
AWS 업데이트 리포트 PDF 생성기 (CLI).

데이터(YAML) + 고정 템플릿(HTML/CSS) -> PDF.
웹앱(webapp/)과 동일한 렌더러(webapp/renderer.py)를 사용하므로
CLI 결과와 웹 미리보기/다운로드 결과가 항상 일치한다.

사용법:
    python generate.py data/2026-06.yml
    python generate.py data/2026-06.yml -o out/report.pdf
    python generate.py data/2026-06.yml --html      # 디버그용 HTML만 저장
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from webapp import renderer

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="AWS 업데이트 리포트 PDF 생성기")
    parser.add_argument("data", help="입력 데이터 YAML 파일 경로")
    parser.add_argument("-o", "--output", help="출력 PDF 경로 (기본: out/<데이터파일명>.pdf)")
    parser.add_argument("--html", action="store_true", help="PDF 대신 중간 HTML을 저장(디버그용)")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"[오류] 데이터 파일을 찾을 수 없습니다: {data_path}", file=sys.stderr)
        return 1

    with data_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    html = renderer.render_html(data)

    out_path = Path(args.output) if args.output else ROOT / "out" / f"{data_path.stem}.pdf"

    if args.html:
        html_path = out_path.with_suffix(".html")
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")
        print(f"[완료] HTML 저장: {html_path}")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = renderer.html_to_pdf_bytes(html)
    out_path.write_bytes(pdf_bytes)
    print(f"[완료] PDF 생성: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
