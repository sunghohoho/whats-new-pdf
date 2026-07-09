"""문서 기본값 (여기서 한 번에 변경).

작성자 등 문서 머리말 기본값을 모아둔다. 환경변수로도 덮어쓸 수 있다.
예: DOC_AUTHOR="플랫폼팀" 으로 실행하면 기본 작성자가 바뀐다.
"""

from __future__ import annotations

import os

# 기본 작성자 (요청: 우선 MSP, 추후 변경 가능)
DEFAULT_AUTHOR = os.getenv("DOC_AUTHOR", "MSP")
DEFAULT_EYEBROW = os.getenv("DOC_EYEBROW", "Infrastructure Notice")
DEFAULT_TITLE = os.getenv("DOC_TITLE", "AWS 서비스 변경사항 안내")
