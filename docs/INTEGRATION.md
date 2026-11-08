# 실제 데이터·모델 연결 안내

## 경계를 유지한 교체

`app/factory.py:create_app(settings=None, repository=None, service="all")`가 조립 지점입니다. 실제 개별 앱은 `app/entrypoints/alerts.py`, `graph.py`, `explanation.py`, `analysis.py`가 자신에게 필요한 HTTP Router만 등록해 생성합니다. 기본 Base URL은 각각 `http://localhost:8001`, `:8002`, `:8003`, `:8004`이며 프론트엔드는 네 주소를 구분합니다.

`app/repositories/base.py:Repository` Protocol을 구현한 저장소를 각 서비스 생성 시 주입하면 HTTP 경로·Pydantic 응답을 유지하면서 저장소를 교체할 수 있습니다. Router는 거래 파일이나 모델을 직접 읽지 않습니다. `app.main:app`은 이전 통합 실행을 위한 호환 진입점으로 남아 있으며 새 분리 구성의 Gateway 역할을 하지 않습니다.

| 담당 | 교체·확장 위치 | 보존할 계약 |
|---|---|---|
| PostgreSQL | `app/repositories/base.py` 구현체, 각 서비스의 `create_app(repository=..., service=...)` 주입 | 거래·예측·설명·유형의 ID와 조회 인터페이스 |
| CSV 적재 | `app/repositories/loader.py`, `scripts/import_csv.py` | 파일 SHA256·행 번호 provenance, 계좌 문자열, 라벨 분리 |
| FraudGT Worker | Prediction을 저장하는 적재 경로, `AlertService` 조회 | `transaction_id`, `fraud_score`, `model_version`; 임계값 후처리 |
| 그래프 저장소 | Repository의 거래 조회·인접 조회 확장과 `GraphService` | 송금 방향·parallel Edge ID·시점 경계·두 seed 계좌의 Hop 정의 |
| GNNExplainer Worker | `ExplanationService.request/get`, 설명 Job 저장소 | 고유 `(transaction_id, model_version)` 작업, 상태·ID·중요도·스냅샷 |
| Typology 모델 | `get_typology()` 결과 적재, `TypologyService` | 독립 유형 신뢰도·버전·미검증 상태·실제 거래 ID 근거 |

현재 `transactions()`는 작은 Fixture를 모두 메모리에서 탐색합니다. 약 950만 행용 운영 조회는 기간·계좌 인덱스와 인접 조회를 저장소에 추가해 제한된 Context만 불러오는 방식으로 교체하세요. CSV 적재 CLI는 전처리 결과를 스트리밍 기록하며, 그 출력이 자동으로 Mock 서버의 예측 데이터로 연결되지는 않습니다.

## 서비스별 실제 구현 전환

프론트엔드에는 `VITE_ALERTS_BASE_URL`, `VITE_GRAPH_BASE_URL`, `VITE_EXPLANATION_BASE_URL`, `VITE_ANALYSIS_BASE_URL`을 전달합니다. 각 값에는 기본적으로 `/api`가 없는 서버 주소를 넣습니다. 상세 사용 코드는 [프론트엔드 연동 안내](FRONTEND_INTEGRATION.md)를 참고하세요. Node·Agent 등 Vite 이외 환경도 같은 네 주소를 환경설정으로 전달할 수 있습니다.

예를 들어 그래프 구현을 실제 DB 조회로 바꿀 때는 graph 앱의 내부 저장소·서비스를 교체하고 동일한 경로와 JSON을 제공합니다. 실제 graph 서비스 주소가 바뀌면 `VITE_GRAPH_BASE_URL`만 변경하고 프론트엔드 개발 서버를 재시작하거나 배포 빌드를 다시 생성합니다. 나머지 세 서비스의 주소와 호출 코드는 유지할 수 있습니다. 설명 POST의 HTTP 202, 작업 ID, 상태 값과 GET 계약도 실제 Worker 연결 후 보존합니다.

현재 4개 앱은 같은 고정 Fixture를 각자의 메모리에 적재하고 서로 HTTP 호출을 하지 않습니다. 원본 거래 ID와 설정이 같아 결과를 연결할 수 있습니다. 실제 배포에서는 버전별 거래·예측·작업 상태를 공유 DB 등에서 조회하도록 바꾸고 각 서비스의 `ALERT_THRESHOLD`, 모델 버전, timezone 정책도 일치시키세요. 프로세스 분리는 개별 실행·교체 경계이며, 같은 PC의 하드웨어 자원을 공유하는 상태에서 처리량 증가를 보장하는 것은 아닙니다.

## FraudGT와 라벨 분리

정규화 거래의 `Transaction`은 `Is_laundering`, `Laundering_type`을 포함하지 않습니다. 이 컬럼은 별도 `GroundTruth`/`labels.jsonl`로 보관합니다. 모델 입력을 만들 때는 특징 허용 목록을 사용해 ID·provenance·정답을 제외하고 실제 모델에서 정의한 수치·범주 특징만 넘기세요.

모델 Node Index는 원본 계좌 문자열과 별도의 매핑입니다. 실제 모델 전처리 결과의 매핑 버전도 모델 입력 그래프와 함께 저장해야 합니다. 거래는 계좌 쌍으로 병합하지 않고 개별 transaction_id를 가진 Directed Multigraph Edge로 유지합니다.

실제 Worker는 동일 transaction_id에 버전별 Prediction을 저장합니다. `ALERT_THRESHOLD` 변경은 점수를 재계산하지 않고 조회 정책만 바꿉니다. 실제 모델 버전 이름을 환경변수에 적는 것만으로 새 예측이 생기는 것은 아닙니다. 해당 버전의 저장된 결과가 필요합니다.

## 예측 당시 그래프 재현

화면 표시용 Subgraph를 다시 추출한 결과가 GNNExplainer 입력과 같다고 가정하지 마세요. 실제 샘플링·Port Numbering·Ego ID·Reverse Message Passing·전처리·Node Index·Edge 속성·checkpoint 버전이 모두 예측 당시와 일치해야 합니다. 현재 `GraphSnapshot`은 그래프 ID, 모델·전처리 버전, 샘플러, seed, Hop·lookback과 정확한 Node/Edge ID를 저장하는 확장 지점입니다.

운영 시에는 graph_id를 불변 모델 입력 아티팩트로 연결하고 실제 텐서·특징·인덱스 매핑·샘플러 설정을 별도 저장하세요. POST 설명은 고유 작업을 내구성 있게 저장한 다음 Worker 큐에 전달하고 GET은 저장된 상태·결과를 조회하도록 바꿉니다. 프로세스 메모리 Job 저장소는 여러 worker와 재시작을 지원하지 않습니다.

중요도 응답은 현재 주변 Context Edge를 중심으로 제공하며 타깃을 제외합니다. 실제 GNNExplainer의 Target Edge Mask 처리 정책을 결정할 때 응답 배열은 개별 transaction_id와 중요도 형태를 유지하고 적용 정책을 스냅샷 메타데이터에 명시하면 됩니다. Graph API의 Edge에 importance를 섞지 않습니다.

## 유형과 Agent 근거

`predicted_type`은 모델 출력이며 정답 라벨·Rule 검증 결과가 아닙니다. 현재 모든 유형 분석은 `unverified`입니다. 원본 SAML-D의 실제 클래스 목록을 검사한 뒤 `app/data/typology_label_mapping.json` 또는 새 버전 매핑 저장소를 구성하세요. 이름이 비슷하다는 이유만으로 자동 매핑하지 않습니다.

분석 근거에는 실제 transaction_id 목록과 실제 송금 방향의 account_path를 저장합니다. 유형 모델이 아직 실행되지 않은 거래는 null로 유지합니다. Agent는 Alert 상세·Graph·Explanation·Analysis의 동일 transaction_id를 결합하고 모델 버전·스냅샷 범위를 함께 전달할 수 있습니다. 이 서버는 Agent나 보고서 API를 제공하지 않습니다.

## 재현과 시간

목록은 `[start,end)`, 그래프는 `[target-lookback,target]`입니다. 사용자가 UTC가 아닌 offset을 보내도 같은 순간으로 비교하며 응답은 UTC입니다. 원본 Date/Time timezone은 입수한 자료에서 확인해야 하며 Mock의 UTC 기본값을 실제 데이터의 속성으로 간주하지 않습니다. CSV 파일 바이트나 timezone 가정이 바뀌는 경우 데이터·전처리 버전도 함께 관리하세요.
