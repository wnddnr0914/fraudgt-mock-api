# FraudGT 기반 AML Mock API

프론트엔드·거래 그래프·Agent 담당자가 모델 개발과 병렬로 사용할 수 있는 **4개 독립 FastAPI 서비스와 총 6개 API**입니다. 거래 조회·그래프·설명·유형 분석을 각각 다른 프로세스와 Base URL에서 직접 호출합니다. 저장된 고정 예측값을 조회하며 실제 FraudGT 추론·학습, GNNExplainer 최적화, 유형 분류, Agent·보고서 생성은 수행하지 않습니다.

기존 `aml-mock-api`와 `gnn-mock-api`는 다른 계약의 프로젝트입니다. 이번 요구사항은 이 `fraudgt-mock-api` 폴더에 독립적으로 구현했습니다.

다른 팀원이 인터넷에서 사용하도록 배포하려면 [Render 배포 안내](docs/RENDER_DEPLOYMENT.md)를 따릅니다. `render.yaml`에 4개 공개 Web Service의 설정을 준비했습니다. 실제 Render 계정에 서비스를 생성하거나 배포한 상태는 아닙니다.

## 설치와 실행

Python **3.11 이상**이 필요합니다. PowerShell에서 이 폴더를 열고 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe scripts\run_services.py --env-file .env
```

가상환경을 활성화하지 않아도 되므로 PowerShell 실행 정책을 바꿀 필요가 없습니다. 이미 `.env`가 있다면 복사 명령은 생략하세요. 실행기는 4개 서비스를 각각 시작하고 Ctrl+C로 함께 종료합니다. 기본 바인딩은 `127.0.0.1`이며 LAN 접속에는 `--host 0.0.0.0`을 추가합니다. `.env`는 `--env-file .env`를 지정할 때 읽으며, 인자 없이 실행하면 기본값 또는 현재 프로세스 환경변수를 사용합니다.

이번에 검증한 직접·간접 의존성 버전을 재현하려면 설치 명령에서 `requirements.txt` 대신 `requirements.lock.txt`를 사용할 수 있습니다.

| 서비스 | Base URL | 담당 API 수 | Swagger |
|---|---|---|---|
| 거래 조회 `alerts` | `http://localhost:8001` | 목록·상세 2개 | [8001/docs](http://localhost:8001/docs) |
| 그래프 `graph` | `http://localhost:8002` | 그래프 1개 | [8002/docs](http://localhost:8002/docs) |
| 설명 `explanation` | `http://localhost:8003` | 요청·결과 2개 | [8003/docs](http://localhost:8003/docs) |
| 유형 분석 `analysis` | `http://localhost:8004` | 분석 1개 | [8004/docs](http://localhost:8004/docs) |

각 주소의 `/openapi.json`도 해당 서비스의 API만 제공합니다. 공통 진입 서버를 거치지 않으며, 예를 들어 그래프 서버에는 거래 목록 API가 없습니다. 4개 서비스는 같은 코드 패키지와 고정 Fixture를 사용하지만 개별 프로세스에서 동작합니다. 다른 PC에 배치할 때도 각 서비스를 개별 실행할 수 있습니다.

서비스 하나만 실행하거나 각각 다른 터미널에서 관리하려면 다음 명령을 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.entrypoints.alerts:app --env-file .env --host 127.0.0.1 --port 8001 --workers 1
.\.venv\Scripts\python.exe -m uvicorn app.entrypoints.graph:app --env-file .env --host 127.0.0.1 --port 8002 --workers 1
.\.venv\Scripts\python.exe -m uvicorn app.entrypoints.explanation:app --env-file .env --host 127.0.0.1 --port 8003 --workers 1
.\.venv\Scripts\python.exe -m uvicorn app.entrypoints.analysis:app --env-file .env --host 127.0.0.1 --port 8004 --workers 1
```

위 4개 명령은 서로 다른 터미널에서 실행합니다. 동일 PC의 동일 포트에 실행기를 중복 시작하지 마세요.

프론트엔드는 [서비스별 환경변수 예시](examples/frontend/.env.example)와 [연동 안내](docs/FRONTEND_INTEGRATION.md)를 사용합니다. URL에는 `/api`를 붙이지 않으며 호출 클라이언트가 기존 API 경로를 추가합니다. 실제 서버로 교체할 때는 해당 서비스의 환경변수 주소를 변경합니다.

기본 CORS 허용 Origin은 `http://localhost:3000,http://localhost:5173`입니다. 프론트엔드를 `127.0.0.1`이나 다른 포트에서 실행한다면 각 서비스가 읽는 `.env`의 `CORS_ORIGINS`에 정확한 프론트엔드 Origin을 추가하세요. 경로 없이 쉼표로 구분합니다. LAN 팀원은 Base URL의 `localhost` 대신 서버 PC의 IP를 사용합니다. 서비스 간 Alert 정책이 같도록 `ALERT_THRESHOLD`, 모델 버전, `SOURCE_TIMEZONE`은 동일하게 설정하세요.

## API 계약

| 서비스·기본 포트 | Method | Endpoint | 기능 |
|---|---|---|---|
| alerts · 8001 | GET | `/api/alerts` | 기간·점수 필터와 페이지네이션 |
| alerts · 8001 | GET | `/api/alerts/{transaction_id}` | 이상거래 상세 |
| graph · 8002 | GET | `/api/alerts/{transaction_id}/graph` | 시점 기준 주변 Directed Multigraph |
| explanation · 8003 | POST | `/api/alerts/{transaction_id}/explanation` | Mock 설명 작업 생성, HTTP 202 |
| explanation · 8003 | GET | `/api/alerts/{transaction_id}/explanation` | 설명 상태와 Edge Importance |
| analysis · 8004 | GET | `/api/alerts/{transaction_id}/analysis` | 유형 예측과 구조화된 근거 |

기존 HTTP 경로와 요청·응답 JSON 계약은 유지했습니다. 상세 JSON은 [API 예시](docs/API_EXAMPLES.md)와 [기계 판독 예시](examples/api_examples.json)에 있습니다. Swagger는 파라미터·응답 모델·필드 설명·오류를 제공합니다. `openapi/` 폴더에 서비스별 계약 사본을 내보내며 루트 `openapi.json`은 기존 통합 앱의 호환용 계약입니다.

```powershell
$alerts = 'http://localhost:8001'
$graph = 'http://localhost:8002'
$explanation = 'http://localhost:8003'
$analysis = 'http://localhost:8004'
Invoke-RestMethod "$alerts/api/alerts?start=2022-11-01T00:00:00Z&end=2022-11-02T00:00:00Z"
Invoke-RestMethod "$alerts/api/alerts/TX000003"
Invoke-RestMethod "$graph/api/alerts/TX000003/graph?hops=2&lookback_days=7"
Invoke-RestMethod "$explanation/api/alerts/TX000003/explanation" -Method Post -ContentType 'application/json' -Body '{"model_version":"fraudgt-mock-v1"}'
Invoke-RestMethod "$explanation/api/alerts/TX000003/explanation"
Invoke-RestMethod "$analysis/api/alerts/TX000003/analysis"
```

POST 본문을 생략하거나 `{}`를 보내면 현재 Alert 예측의 모델 버전을 사용합니다. GET 설명 결과에도 선택적 `model_version` 쿼리를 사용할 수 있습니다. 준비되지 않은 모델 버전을 요청하면 409를 반환합니다.

### 목록과 오류 정책

`start`, `end`는 timezone이 포함된 ISO 8601 필수값입니다. 내부 비교는 UTC이며 목록 범위는 **`start <= timestamp < end`**입니다. `page`는 1부터, `page_size`는 기본 20·최대 100입니다. 정렬은 timestamp 내림차순, 동률이면 transaction_id 내림차순입니다. `total`은 페이지 제한 전 개수이며 빈 결과·범위 밖 페이지는 정상 200과 빈 배열입니다.

서버 `ALERT_THRESHOLD` 기본값은 0.8입니다. 목록의 `min_score`는 추가 하한으로 작동하므로 0으로 지정해도 서버 임계값 아래 거래는 목록에 들어오지 않습니다. 상세·Graph·Explanation·Analysis도 동일한 Alert 정책을 적용합니다. 거래가 존재해도 임계값 아래이거나 현재 버전 예측이 없으면 **404**입니다.

| HTTP | 상황 |
|---|---|
| 400 | 시작이 종료보다 늦거나 같은 기간 |
| 404 | 없는 거래 또는 Alert 조회 대상이 아닌 거래 |
| 409 | 저장된 Alert 예측과 설명 요청의 모델 버전 불일치 |
| 422 | timezone 누락, 잘못된 날짜·페이지·점수·Hop 등 |
| 500 | 예상하지 못한 내부 처리 오류; 세부 예외는 응답에 노출하지 않음 |

오류 응답은 `{"error":{"code":"...","message":"...","details":[]}}`입니다. 설명을 요청하지 않은 상태는 오류가 아닌 HTTP 200 `not_requested`입니다.

## 공통 데이터와 예시 시나리오

원본 SAML-D CSV는 현재 접근 가능한 프로젝트에 없습니다. 과거 검사 결과 JSON은 남아 있지만 이번 Fixture는 그 원본 행을 복제한 데이터가 아닙니다. `app/data/mock_transactions.json`의 **31건은 직접 만든 합성 거래**이며 SAML-D와 같은 12개 원본 컬럼을 갖습니다. 계좌·통화·유형 라벨도 Mock 개발용입니다. [SAML-D 제공 페이지](https://www.kaggle.com/datasets/berkanoztas/synthetic-transaction-monitoring-dataset-aml)는 원본 데이터의 출처 참고용입니다.

- 기간: 2022-10-24 ~ 2022-11-03. 11월 1일과 11월 2~3일을 각각 조회하면 다른 Alert를 확인할 수 있습니다.
- `TX000001` A→B, `TX000002` C→B, `TX000003` B→D: Fan-In 후보와 후속 송금 관찰.
- `TX000004` D→E, `TX000005` E→F, `TX000006` F→D: 뒤 시점의 Cycle 후보.
- A→B 반복 거래와 값까지 같은 원본 행을 별도 ID로 유지해 Multigraph를 테스트합니다.
- `TX000017`: Alert이지만 유형 분석이 없어 `typology: null`, `evidence: null`.
- `TX000018`: 설명 POST 후 GET에서 `failed`가 되는 고정 실패 시나리오.
- `TX000030`: TX000003보다 정확히 7일 전인 경계 거래. `TX000031`: 1초 뒤의 미래 거래로 TX000003 그래프에서 제외됩니다.

`mock_predictions.json`, `mock_typologies.json`, `mock_explanations.json`은 공통 거래 ID를 참조합니다. 저장소가 적재 시 참조·범위·경로·시간·버전을 검증합니다. 점수와 중요도는 실행마다 바뀌지 않습니다. `Fan-In`, `Fan-Out`, `Cycle`, `Layering` 등의 모델 출력 예시를 실제 SAML-D의 원본 `Laundering_type` 클래스와 동일하다고 가정하지 않습니다. `typology_label_mapping.json`이 향후 명시적 라벨 매핑을 위한 위치입니다.

원본 `Date`와 `Time`은 timezone 정보가 없으므로 `SOURCE_TIMEZONE`을 사용해 결합·변환합니다. 기본 UTC는 **이 Mock의 시간 가정**이며 실제 SAML-D가 UTC라고 주장하지 않습니다. timezone 설정을 바꾸면 같은 원본 벽시각이 가리키는 UTC 시각이 달라집니다. 반복 가능한 검증에는 기본값을 사용하세요.

### 거래 ID와 정답 분리

합성 Fixture는 파일 내 논리 행 순서에 대응하는 `TX000001` 형식을 사용합니다. 서로 같은 계좌·금액·시간의 행도 별도 거래입니다. 원본 파일 식별값·파일명·1부터 시작하는 논리 CSV 행 번호를 provenance로 보존합니다.

실제 CSV 로더는 **파일 바이트 전체의 SHA256 + 논리 행 번호**를 사용한 `TX_<full-sha256>_<row>` 형식을 생성합니다. 동일한 바이트의 CSV를 다른 경로에서 다시 불러와도 ID가 유지됩니다. 파일 내용이나 줄바꿈이 바뀌면 별도의 소스 네임스페이스가 됩니다. 모델 노드 인덱스는 원본 계좌 ID와 별도로 보관합니다.

`Is_laundering`, `Laundering_type`은 `GroundTruth`로 분리하고 추론용 `Transaction` 특징과 API에 넣지 않습니다. Mock Prediction도 정답 라벨에서 계산하지 않습니다. 실제 모델 연결 시에는 provenance·ID·라벨도 모델 수치 특징에 자동으로 포함하지 마세요.

## 그래프와 설명의 차이

Graph API는 타깃의 송금·수취 계좌를 **hop 0**으로 놓고 들어오는 연결과 나가는 연결을 모두 탐색합니다. 탐색된 계좌 집합 안의 거래를 반환하되 송금 방향·개별 Edge ID를 유지합니다. 기본 2-Hop, 7일이며 `hops=1..3`, `lookback_days=1..30`입니다. 시간 범위는 **`target_time - lookback <= context_time <= target_time`**로 양 끝을 포함합니다. 타깃은 항상 포함하고 미래 거래는 제외합니다. Graph 응답에는 중요도가 없습니다.

설명은 화면 조회와 별개로 **예측 당시의 고정 입력 그래프 스냅샷**을 참조합니다. GET 설명의 `graph_snapshot`은 그래프 ID, 모델·전처리 버전, 샘플러, seed, 당시 노드·Edge ID와 탐색 설정을 전달합니다. 현재 Mock 스냅샷은 기본 2-Hop·7일 화면 그래프에 매핑되도록 준비되어 있습니다. 화면의 Hop·기간을 변경해도 설명 스냅샷은 변경되지 않습니다. 화면에 없는 중요 거래가 있을 수 있으므로 프론트엔드는 Edge ID로 교집합을 매핑하고 스냅샷 범위를 확인해야 합니다.

설명 상태는 `not_requested → pending → completed` 또는 `failed`입니다. POST는 작업을 만들고 202를 반환합니다. 첫 GET이 준비된 결과로 상태를 전환하며 실제 지연·최적화는 없습니다. 동일 거래·모델 버전의 POST는 같은 explanation_id와 작업을 재사용하며 이미 완료된 작업의 상태를 되돌리지 않습니다. `fraud_score`는 이상 점수, `edge_importance`는 예측을 설명하는 주변 거래의 중요도, `typology.confidence`는 별도 유형 예측 신뢰도입니다. 세 값을 같은 의미로 사용하지 마세요.

각 서비스는 같은 Fixture를 자기 저장소에 적재하며 다른 서비스로 HTTP 요청을 보내지 않습니다. 설명 작업 상태는 설명 서비스 메모리에만 저장되어 재시작 시 `not_requested`로 초기화됩니다. 여러 Uvicorn worker 간에는 상태가 공유되지 않으므로 현재 설명 Mock은 **`--workers 1`**로 실행합니다. 서비스 프로세스를 나누는 것만으로 같은 컴퓨터의 CPU·RAM·GPU가 분리되지는 않습니다.

## 실제 CSV 추가와 모델·DB 확장

실제 파일이 있으면 다음 명령으로 컬럼·값을 검사하면서 스트리밍 정규화합니다. 출력 폴더는 기존 파일을 덮어쓰지 않는 새 경로를 사용하세요.

```powershell
.\.venv\Scripts\python.exe scripts\import_csv.py 'C:\data\SAML-D.csv' --output '.\data\samld-import' --source-timezone UTC
```

`transactions.jsonl`, `labels.jsonl`, `node_map.jsonl`, `metadata.json`을 생성하며 계좌 식별자 문자열·중복 거래·출처·원본 라벨 분리를 유지합니다. 날짜·시간·금액·필수 컬럼·0/1 라벨 등을 검사합니다. 실제 원본 timezone이 확인되면 `--source-timezone`을 그 기준으로 지정하세요. 원본 클래스는 `metadata.json`에서 확인하고 매핑을 확정하세요.

이 명령은 **데이터 적재 전처리**입니다. 실제 CSV의 거래를 현재 서버가 자동으로 서비스하거나 고정 Mock 점수를 붙이지 않습니다. 실제 데이터 규모에서는 적재 결과를 PostgreSQL에 저장하고 동일 ID를 사용하는 실제 예측·설명·유형 결과를 별도로 저장한 Repository를 주입해야 합니다. 연결 예시는 [확장 안내](docs/INTEGRATION.md)에 있습니다.

## 프로젝트 구조

```text
fraudgt-mock-api/
├── app/
│   ├── factory.py              # 공통 앱 조립, 오류, CORS
│   ├── deployment.py           # 서비스 실행 정보
│   ├── entrypoints/            # alerts·graph·explanation·analysis 개별 앱
│   ├── main.py                 # 기존 통합 앱 호환 진입점
│   ├── config.py               # 검증된 설정·환경변수
│   ├── errors.py               # 공통 오류 계약
│   ├── api/                   # 여섯 HTTP 경로, 요청 검증
│   ├── schemas/               # Pydantic v2 입력·출력·내부 모델
│   ├── services/              # Alert·Graph·Explanation·Typology
│   ├── repositories/          # Protocol, Mock 저장소, CSV 로더
│   └── data/                  # 거래·점수·설명·유형·라벨 매핑 JSON
├── tests/                     # API·로더 Pytest 검증
├── scripts/                   # CSV 적재, 실행 서버 점검, 계약 내보내기
├── docs/                      # API 예시·확장 안내·검증 기록
├── examples/                   # 서비스별 URL 클라이언트·JSON 예시
├── openapi/                    # 서비스별 OpenAPI 사본
├── openapi.json
├── render.yaml                # Render Web Service 4개 배포 설정
├── requirements.txt
└── .env.example
```

요청은 `API Router → Service → Repository Protocol → MockRepository` 순으로 처리합니다. Router가 Fixture를 읽거나 그래프를 탐색하지 않습니다. PostgreSQL·Worker 연결은 Repository·Service 경계에서 교체합니다.

## 검증과 계약 갱신

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\export_contract.py
# 서버가 실행 중인 다른 터미널에서:
.\.venv\Scripts\python.exe scripts\smoke_test.py
# 실행 중인 서버가 없는 경우, 네 서비스를 시작·점검·종료까지 한 번에 수행:
.\.venv\Scripts\python.exe scripts\run_services.py --smoke-test
```

테스트는 기간·timezone·임계값·페이지네이션, Alert 정책, Hop·lookback·경계·미래 정보 제외, 반복 거래와 ID 참조, 설명 상태·멱등성·실패, 분석 경로·누락, CORS·OpenAPI·안전한 오류 응답과 CSV ID 재현성을 검증합니다. 실제 실행 결과는 [검증 기록](docs/VALIDATION.md)에 정리합니다. 외부 서버 배포와 실제 모델·DB 연동은 이번 범위에 포함하지 않습니다.

다른 주소에서 실행 중인 서비스를 점검할 때는 `smoke_test.py`의 `--alerts-base-url`, `--graph-base-url`, `--explanation-base-url`, `--analysis-base-url` 옵션으로 각 주소를 전달할 수 있습니다.

Node.js가 설치되어 있으면 전체 Pytest에서 서비스별 URL 클라이언트의 JavaScript 테스트도 실행합니다. Node.js가 없으면 해당 선택적 예제 테스트만 skip하며 Python API 서버 실행에는 영향을 주지 않습니다.

## 기존 통합 앱 호환 실행

이전 호출 코드를 점검할 때만 `python -m uvicorn app.main:app --port 8000 --workers 1`을 사용할 수 있습니다. 이 통합 앱은 자동으로 실행되지 않으며, 위 4개 서비스의 앞에서 요청을 전달하는 Gateway도 아닙니다. 신규 프론트엔드·Agent 연동은 서비스별 Base URL을 기준으로 작성하세요.
