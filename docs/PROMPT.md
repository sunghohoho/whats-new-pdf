# 스크립트 표준화 프롬프트 (입력 통일)

엔지니어마다 붙여넣는 스크립트 형식이 달라 파싱이 흔들리는 문제를 근본적으로 없애려면,
**스크립트를 생성하는 AI에게 아래 형식을 강제**하세요. 이 형식은 웹앱 파서(규칙 기반/LLM 둘 다)가
가장 일관되게 인식하도록 설계되어 있습니다.

- 표준 형식으로 뽑으면 → LLM 없이 규칙 파서만으로도 거의 완벽히 파싱
- 표준을 안 지켜도 → LLM 자동 파싱이 아래와 동일한 규칙으로 정규화 (`webapp/llm_parser.py`)

즉 **파서와 생성 프롬프트가 같은 규칙**을 공유하므로 결과가 일관됩니다.

---

## 상위 AI에게 주는 생성 프롬프트

아래를 복사해 스크립트 생성용 AI(사내 어시스턴트/Claude 등)에 시스템 지시로 넣으세요.

```
아래 규칙에 맞춰 "AWS 서비스 변경사항"을 정리해줘. 형식과 섹션 순서를 반드시 지켜라.

[공통 규칙]
- 날짜는 YYYY.MM.DD 로 통일 (연-월까지만 알면 YYYY.MM).
- AWS 공식 발표(What's New) 원문 기준으로만 요약. 내부 코멘트/고객사명/코드네임/프로젝트명 금지.
- 섹션 순서는 항상 EOL/EOS → NEW.
- 마크다운 문법(#, **, 표) 쓰지 말고 아래 골격의 순수 텍스트로.

[EOL / EOS 골격]
EOL / EOS

EOL
<서비스명> <버전(있으면)> — <종료일> 종료 → <전환 대상>
# 전환 대상이 없고 여러 서비스가 같은 날 종료면 한 줄로 묶기:
<서비스1> · <서비스2> · <서비스3> — <종료일> 종료

Maintenance
<서비스1> · <서비스2> · <서비스3> — <차단일> 신규 가입 차단 (기존 고객만 유지)
# 차단일이 다른 항목은 개별 표기:
<서비스> — <차단일> 신규 가입 차단

SDK / 도구
<항목> — <종료일> EOS

[NEW 골격]  (발표일 최신순)
<서비스명> (<GA 또는 PREVIEW 있으면>, <발표일>)
<한 줄 요약 1>
<한 줄 요약 2 — 있으면>
<공식 링크>

<서비스명2> (<발표일>)
...
<공식 링크>

[규칙 상세]
- 서비스명과 버전은 이어서 적되(예: "Aurora MySQL 3.05 / 3.06"), 파서가 자동 분리한다.
- EOL = 운영 종료(서비스 완전 종료, 마이그레이션 필수), Maintenance = 신규가입 중단, SDK/도구 = EOS.
- NEW 배지는 GA/PREVIEW가 공식 발표에 명시된 경우에만 괄호 안에 표기. 추측 금지.
- 한 발표에 세부 항목이 여러 개(각각 링크)면 제목 아래에 들여쓰기해 나열.
```

---

## 표준 형식 예시

```
EOL / EOS

EOL
AWS WAF Classic — 2026.10.07 종료 → WAFv2
AWS App Mesh — 2026.09.30 종료 → ECS Service Connect
FinSpace · Fraud Detector · Lookout for Equipment — 2026.10.07 종료

Maintenance
App Runner · Audit Manager · IoT FleetWise — 2026.04.30 신규 가입 차단 (기존 고객만 유지)
CloudTrail Lake — 2026.05.31 신규 가입 차단

SDK / 도구
AWS SDK for .NET v3.x — 2026.06.01 EOS

NEW

Amazon OpenSearch Serverless (GA, 2026.05.28)
컴퓨팅/스토리지 분리, scale-to-zero로 최대 60% 절감
https://aws.amazon.com/about-aws/whats-new/2026/05/amazon-opensearch-serverless-next-generation-generally-available/

Claude Opus 4.8 on AWS (2026.05.28)
Anthropic 최상위 모델, 1M 토큰 컨텍스트·128K 출력, Bedrock 제공
https://aws.amazon.com/about-aws/whats-new/2026/05/claude-opus-4.8-aws/
```

이 형식으로 붙여넣으면 파싱 결과가 매번 동일한 구조로 나옵니다.

---

## (선택) 화이트리스트 / 제외 필터

원본 템플릿에는 `whitelist_services.yaml`(포함할 서비스), `exclude_patterns.yaml`(제외할
내부명/고객사/코드네임) 개념이 있습니다. 우리 앱에는 아직 넣지 않았습니다.
필요하면 파싱 후 서버에서 필터링하는 기능으로 추가할 수 있으니 요청 주세요.
