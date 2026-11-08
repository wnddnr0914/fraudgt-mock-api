# 검증 기록

검증일: **2026-11-08 (Asia/Seoul)**. Python **3.13.7**, FastAPI **0.141.1**, Pydantic **2.13.4**, Uvicorn **0.52.3**, Pytest **9.2.0**, HTTPX **0.28.1** 환경에서 확인했습니다. 프로젝트 요구 Python 범위는 3.11 이상이며, 이번 실행 검증은 3.13.7에서 수행했습니다.

## 서비스 분리 변경 검증

현재 기본 실행 구성은 `alerts:8001`, `graph:8002`, `explanation:8003`, `analysis:8004`의 4개 독립 앱입니다. 이 구성을 대상으로 전체 Pytest와 실제 4개 HTTP 서버 점검을 완료했습니다.

```text
python -m pytest -q
88 passed in 5.05s
```

전체 테스트에는 기존 거래·그래프·설명·유형·CSV 계약과 함께 서비스별 Router·OpenAPI 격리, 기존 통합 앱과 응답 JSON 일치, 서비스 간 거래 ID 연결, 개별 CORS·Swagger 및 프론트엔드 클라이언트 검증이 포함됩니다. 프론트엔드의 네 주소 라우팅·Vite 환경변수 매핑·HTTP 오류·설명 상태 대기는 별도 Node 테스트 **12개**도 통과했습니다. 전체 Pytest에는 이 Node 테스트를 실행하는 래퍼 테스트가 포함됩니다.

```powershell
.\.venv\Scripts\python.exe scripts\run_services.py --smoke-test
```

위 명령은 서로 다른 프로세스 4개를 실제 포트 8001~8004에 시작했고, **8.29초에 통과**한 뒤 소유한 4개 서비스를 모두 종료했습니다.

| 실제 분리 실행 점검 | 결과 |
|---|---|
| alerts 목록·상세, graph 조회, explanation GET, analysis 조회 | HTTP 200 |
| explanation POST | HTTP 202 |
| 서비스별 `/docs` | 4개 모두 HTTP 200 |
| 서비스별 `/openapi.json` | 4개 모두 HTTP 200, 담당 API 수 2·1·2·1개 |
| 서비스별 CORS preflight | 4개 모두 HTTP 200, 허용 Origin 헤더 일치 |
| Graph·Explanation·Analysis와 거래 조회의 Transaction ID | 일치 |
| 실행기 종료 후 소유한 서버 프로세스 | 4개 모두 종료 |

`python scripts/export_contract.py`도 성공했으며 서비스별 OpenAPI 4개, 통합 앱 호환 계약, 실제 서비스별 Base URL이 포함된 JSON·Markdown 예시를 생성했습니다. 현재 검증 서버는 실행 상태로 남겨두지 않았습니다. README의 실행 명령으로 네 서비스를 시작하면 됩니다.

아래 72개 테스트와 포트 8000의 결과는 분리 전 계약의 기준선입니다.

## 기존 계약의 검증 기준선

```text
python -m pytest -q
72 passed in 3.16s
```

테스트에는 다음이 포함됩니다.

- 기간 시작 포함·종료 제외, 서로 다른 조회 기간, timezone offset 동등성, 최신순 정렬.
- 서버 임계값과 min_score, 페이지별 결과·전체 개수, 빈 결과.
- 존재하지 않는 거래·임계값 아래 거래의 404, 역전 기간 400, 잘못된 요청 422, 내부 오류 500.
- 타깃 포함, 1-Hop·2-Hop 차이, 1일·7일 차이, 정확히 7일 전 경계 포함, 미래 거래 제외.
- 동일 계좌·동일 값 반복 거래 보존, 모든 Graph Edge의 ID·방향·금액·시각과 공통 거래 저장소 일치.
- 설명 `not_requested → pending → completed`, 동일 거래·버전 멱등성, 안정적 중요도, 고정 스냅샷, 실패 상태.
- 분석 누락 시 null, 모든 분석의 거래 ID·송금 방향 경로·시간 일치.
- CORS와 6개 OpenAPI 경로, CSV의 필수 컬럼·값·timezone 검사, ID 재현성·중복 보존·라벨 분리.

CSV 메타데이터의 원본 유형·정답값별 집계도 확인했으며 로더 테스트 18개가 최종 변경 후 다시 통과했습니다. 정확한 설치 버전 전체는 `requirements.lock.txt`에 보관했습니다.

Starlette의 HTTPX TestClient 호환 경고 1건이 있었으며 테스트 실패는 없었습니다. 이 작업 실행 환경의 제한된 sandbox는 Windows 이벤트 루프의 로컬 socketpair를 막아 TestClient가 대기하는 현상이 있어, 테스트를 로컬 네트워크 접근이 허용된 실행 환경에서 수행했습니다. 일반적인 프로젝트 실행 명령이나 애플리케이션 코드를 변경할 필요는 없습니다.

## 문서와 계약

`python scripts/export_contract.py`를 실행해 실제 TestClient 응답에서 다음을 생성했습니다.

- `openapi/alerts.json`, `openapi/graph.json`, `openapi/explanation.json`, `openapi/analysis.json`
- `openapi.json`: 기존 통합 앱 호환 계약
- `app/api/response_examples.json`: 실행 중인 Swagger의 성공 응답 JSON 예시
- `examples/api_examples.json`: 서비스·Base URL·전체 요청 URL 포함
- `docs/API_EXAMPLES.md`

2022-11-01 기간 목록은 기본 임계값에서 Alert **7건**입니다. TX000003 기본 2-Hop·7일 그래프는 **11개 거래 Edge**를 포함합니다. 중요도는 같은 거래 ID로 연결되며 Graph 응답 자체에는 importance 필드가 없습니다.

## 기존 통합 실행 서버의 검증 기준선

Uvicorn을 실제로 시작해 `http://127.0.0.1:8000`에서 아래 명령을 실행했고 **통과**했습니다.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py --base-url http://127.0.0.1:8000
```

| 점검 | 결과 |
|---|---|
| GET 기간 목록·TX000003 상세·Graph | 모두 HTTP 200 |
| POST Explanation | HTTP 202, 작업 ID 반환 |
| GET Explanation | HTTP 200, completed와 중요도 반환 |
| GET Analysis | HTTP 200, 유형·거래 ID·계좌 경로 반환 |
| GET `/docs` | HTTP 200, Swagger HTML 제공 |
| GET `/openapi.json` | HTTP 200, 업무 API 총 6개 동작 |
| OPTIONS 프론트엔드 CORS preflight | HTTP 200, 허용 Origin 헤더 일치 |
| 각 실제 HTTP 응답의 CORS Origin 및 Swagger 성공 JSON 예시 6개 | 일치 |
| Graph·Explanation·Analysis 거래 ID 연결 | 일치 |

이 점검은 실행 서버에 실제 HTTP 요청을 보내 수행했습니다. Mock 모델을 호출하거나 외부 서버에 배포하지 않았습니다.

위 검증용 통합 서버는 점검 후 종료했습니다. 현재 기본 실행은 README의 `scripts/run_services.py` 명령으로 네 개 포트에서 시작합니다.

## 검증 범위

Render 배포 준비 파일도 별도로 확인했습니다. `render.yaml`의 YAML 구문, 네 서비스의 `plan: free`, 공통 환경변수 그룹 참조, Build Command의 의존성 파일, Start Command가 참조하는 실제 앱, Health Check 경로를 검사했습니다. 서비스별 OpenAPI는 각각 2·1·2·1개로 총 6개 업무 API를 유지합니다. 배포 후 점검 스크립트에는 조정 가능한 HTTP `--timeout`을 추가하고 명령행 파싱·문법 검증을 수행했습니다. Render 계정에서 Blueprint를 생성하거나 원격 빌드·배포·공개 URL을 검증한 것은 아닙니다.

소규모 합성 Fixture, Mock 예측·설명·유형 결과, CSV 스트리밍 전처리를 검증했습니다. 실제 SAML-D 원본 전량 적재, 950만 건 조회 성능, FraudGT·GNNExplainer·유형 모델, PostgreSQL, Agent, 외부 서버 배포는 수행하지 않았습니다.
