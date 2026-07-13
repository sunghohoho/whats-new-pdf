"""URL 유효성 검사 모듈.

렌더링/PDF 생성 전에 whats_new 항목의 URL이 살아있는지 HEAD 요청으로 확인한다.
404/연결불가 URL은 dead=True 플래그를 붙여 템플릿이 취소선+경고로 표시할 수 있게 한다.

- 병렬 처리: concurrent.futures ThreadPoolExecutor
- 타임아웃: 5초 (느린 AWS 페이지 고려)
- 리다이렉트는 따라가며 최종 상태코드로 판단
- 오류(연결불가/DNS 실패 등)도 dead 처리
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("aws_report_studio")

_TIMEOUT = 5
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; aws-report-studio/1.0; url-check)"}
_MAX_WORKERS = 8


def _check_one(url: str) -> tuple[str, bool, int | None]:
    """(url, is_dead, status_code) 반환. is_dead=True이면 404/오류."""
    if not url or not url.startswith("http"):
        return url, False, None
    try:
        req = Request(url, method="HEAD", headers=_HEADERS)
        with urlopen(req, timeout=_TIMEOUT) as resp:
            code = resp.status
            return url, code >= 400, code
    except HTTPError as e:
        return url, e.code >= 400, e.code
    except URLError as e:
        logger.debug("URL 연결 실패 %s: %s", url, e)
        return url, True, None
    except Exception as e:
        logger.debug("URL 확인 오류 %s: %s", url, e)
        return url, True, None


def check_urls(data: dict) -> dict:
    """data 내 whats_new 의 모든 URL을 병렬 체크해 결과를 반영한 data를 반환.

    각 항목에 url_status: {"url": ..., "dead": bool, "code": int|None} 를 추가.
    """
    # 수집
    targets: list[str] = []
    for item in data.get("whats_new") or []:
        if item.get("url"):
            targets.append(item["url"])
        for sub in item.get("subitems") or []:
            if sub.get("url"):
                targets.append(sub["url"])

    if not targets:
        return data

    # 병렬 체크
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(targets))) as pool:
        futures = {pool.submit(_check_one, u): u for u in set(targets)}
        for fut in as_completed(futures):
            url, dead, code = fut.result()
            results[url] = {"url": url, "dead": dead, "code": code}
            if dead:
                logger.warning("죽은 링크 감지: %s (code=%s)", url, code)

    # 결과 반영
    for item in data.get("whats_new") or []:
        if item.get("url"):
            item["url_status"] = results.get(item["url"], {"dead": False, "code": None})
        for sub in item.get("subitems") or []:
            if sub.get("url"):
                sub["url_status"] = results.get(sub["url"], {"dead": False, "code": None})

    return data
