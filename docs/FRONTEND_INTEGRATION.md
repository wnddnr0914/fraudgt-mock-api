# 서비스별 Base URL로 프론트엔드 연결

Mock부터 거래 조회·그래프·설명·유형 분석의 호출 주소를 구분합니다. 프론트엔드는 서비스별 클라이언트 메서드를 사용하고, 실제 서비스의 배포 주소가 정해지면 환경변수 값만 교체합니다. HTTP 메서드·API 경로·요청 및 응답 JSON은 현재 계약을 유지해야 합니다.

## 주소 설정

기존 프론트엔드 프로젝트의 환경변수 파일에 [예시](../examples/frontend/.env.example)를 반영합니다. 이 파일은 백엔드의 `.env`와 용도가 다릅니다.

```dotenv
VITE_ALERTS_BASE_URL=http://localhost:8001
VITE_GRAPH_BASE_URL=http://localhost:8002
VITE_EXPLANATION_BASE_URL=http://localhost:8003
VITE_ANALYSIS_BASE_URL=http://localhost:8004
```

기본 Base URL에는 `/api`를 붙이지 않습니다. 클라이언트가 `/api/alerts/...` 경로를 추가합니다. Vite 환경변수 변경 후에는 개발 서버를 재시작하고, 배포 빌드는 다시 생성하세요. LAN 접속에는 API 서버 PC의 IP 또는 DNS를 사용합니다.

| 클라이언트 메서드 | 환경변수 | 실제 호출 경로 |
|---|---|---|
| `listAlerts()` | `VITE_ALERTS_BASE_URL` | `GET /api/alerts` |
| `getAlert()` | `VITE_ALERTS_BASE_URL` | `GET /api/alerts/{id}` |
| `getGraph()` | `VITE_GRAPH_BASE_URL` | `GET /api/alerts/{id}/graph` |
| `requestExplanation()` | `VITE_EXPLANATION_BASE_URL` | `POST /api/alerts/{id}/explanation` |
| `getExplanation()` | `VITE_EXPLANATION_BASE_URL` | `GET /api/alerts/{id}/explanation` |
| `getAnalysis()` | `VITE_ANALYSIS_BASE_URL` | `GET /api/alerts/{id}/analysis` |

## Vite 프로젝트에서 사용

[클라이언트](../examples/frontend/aml-client.mjs)와 [Vite 어댑터](../examples/frontend/vite-client.js)를 프론트엔드의 같은 폴더, 예를 들어 `src/api/`에 넣습니다. 아래 예시는 `src/main.js`에서 불러오는 경우입니다.

TypeScript에서 입력·응답 타입을 함께 사용하려면 같은 폴더의 `aml-client.d.mts`도 복사합니다. 이 클라이언트는 추가 npm 패키지를 요구하지 않습니다.

```javascript
import { createViteAmlClient } from "./api/vite-client.js";

const aml = createViteAmlClient();
const page = await aml.listAlerts({
  start: "2022-11-01T00:00:00Z",
  end: "2022-11-02T00:00:00Z",
  page: 1,
  pageSize: 20,
});

const transactionId = "TX000003";
const [detail, graph, analysis] = await Promise.all([
  aml.getAlert(transactionId),
  aml.getGraph(transactionId, { hops: 2, lookbackDays: 7 }),
  aml.getAnalysis(transactionId),
]);

await aml.requestExplanation(transactionId, {
  modelVersion: detail.model_version,
});
const explanation = await aml.waitForExplanation(transactionId, {
  modelVersion: detail.model_version,
  pollIntervalMs: 500,
  timeoutMs: 60_000,
});

if (explanation.status === "failed") {
  console.error(explanation.error);
} else {
  const importanceById = new Map(
    explanation.edge_importance.map(edge => [edge.transaction_id, edge.importance]),
  );
  // graph.graph.edges의 edge.id와 importanceById의 키는 같은 transaction_id입니다.
  console.log(page, detail, graph, analysis, importanceById);
}
```

위 예제의 중요도 매핑 키는 `graph.graph.edges[*].id`와 `edge_importance[*].transaction_id`입니다. 그래프의 Hop·기간을 좁히면 설명 스냅샷의 일부 Edge가 화면에 없을 수 있으므로 화면 Edge와 ID가 일치하는 결과만 표시합니다.

설명은 `not_requested`, `pending`, `completed`, `failed` 상태를 갖습니다. `waitForExplanation()`은 요청 후 `completed` 또는 `failed`가 될 때까지 조회하며, `not_requested`·시간 초과·취소는 예외로 전달합니다. HTTP 202 자체가 설명 계산 완료를 뜻하지 않습니다. 화면을 닫거나 거래 선택이 바뀌는 경우에는 `AbortController`의 `signal`을 전달해 대기 중인 호출을 취소할 수 있습니다. [전체 사용 예제](../examples/frontend/demo.js)도 함께 제공합니다.

## Vite 이외 환경

기본 클라이언트는 브라우저 또는 `fetch`를 제공하는 Node 환경에서 사용할 수 있으며 Vite에 의존하지 않습니다.

```javascript
import { createAmlClient } from "./examples/frontend/aml-client.mjs";

const aml = createAmlClient({
  alertsBaseUrl: process.env.ALERTS_BASE_URL,
  graphBaseUrl: process.env.GRAPH_BASE_URL,
  explanationBaseUrl: process.env.EXPLANATION_BASE_URL,
  analysisBaseUrl: process.env.ANALYSIS_BASE_URL,
});
const result = await aml.getAnalysis("TX000003");
```

주소는 호출자의 환경설정에서 전달합니다. 빠진 주소는 클라이언트 생성 시 오류로 처리하므로 여러 서비스가 실수로 공통 주소 하나에 연결되는 기본값은 없습니다. Python Agent도 같은 네 개의 Base URL을 설정으로 받아 동일한 HTTP 경로를 호출하면 됩니다.

## 실제 모델 서비스로 전환

예를 들어 실제 graph 서비스의 주소가 `https://graph.example.org`가 되면 `VITE_GRAPH_BASE_URL`을 그 주소로 바꿉니다. `aml.getGraph()` 호출 코드는 유지하며, 다른 서비스는 각각 준비되는 시점에 주소를 교체할 수 있습니다. 이 주소는 설명용 예시이며 배포된 서비스가 아닙니다.

각 실제 서비스는 해당 경로·JSON·오류·상태 계약을 유지해야 합니다. 그래프 조회, 설명 실행, 유형 분석의 내부 모델이나 DB가 달라지는 것은 각 백엔드 구현에서 처리합니다. 운영의 실제 계산 시간이 길어져도 프론트엔드는 이미 준비한 설명 상태 처리와 대기 흐름을 사용할 수 있습니다.

브라우저 호출을 허용하려면 모든 서비스의 `CORS_ORIGINS`에 프론트엔드의 정확한 Origin을 설정합니다. 예를 들어 `http://localhost:5173`과 `http://127.0.0.1:5173`은 서로 다른 Origin입니다.
