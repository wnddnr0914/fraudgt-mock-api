# 서비스별 Base URL 클라이언트

이 폴더의 코드를 기존 프론트엔드에 복사해 사용할 수 있습니다. UI나 npm 패키지를 추가하지 않는 Fetch 클라이언트입니다.

`aml-client.mjs`는 주소 네 개를 받아 6개 엔드포인트를 담당 서비스로 호출합니다. 주소는 Origin 또는 프록시 경로 prefix이며 **`/api`를 포함하지 않습니다**. 예를 들어 그래프 서버가 `https://graph.example.com`이면 요청은 `https://graph.example.com/api/alerts/{id}/graph`가 됩니다. `https://example.com/graph-service`와 같은 prefix도 지원합니다.

| 환경변수 | Mock 주소 | 담당 |
|---|---|---|
| `VITE_ALERTS_BASE_URL` | `http://localhost:8001` | 목록·상세 |
| `VITE_GRAPH_BASE_URL` | `http://localhost:8002` | 그래프 |
| `VITE_EXPLANATION_BASE_URL` | `http://localhost:8003` | 설명 요청·결과 |
| `VITE_ANALYSIS_BASE_URL` | `http://localhost:8004` | 유형 분석 |

Vite 프론트엔드 프로젝트의 `.env`에 `.env.example`의 값을 넣고 개발 서버를 다시 시작합니다. `vite-client.js`의 `createViteAmlClient()`를 호출하면 환경변수를 읽습니다. 값이 빠져 있으면 즉시 오류를 내므로 공통 주소로 몰래 돌아가지 않습니다. Vite 환경변수는 빌드 시 반영되므로 배포 환경 주소를 바꾼 뒤에는 프론트엔드를 다시 빌드합니다.

```javascript
import { createViteAmlClient } from "./vite-client.js";

const aml = createViteAmlClient();
const detail = await aml.getAlert("TX000003");
const graph = await aml.getGraph("TX000003", { hops: 2, lookbackDays: 7 });
await aml.requestExplanation("TX000003", { modelVersion: detail.model_version });
const explanation = await aml.waitForExplanation("TX000003", {
  modelVersion: detail.model_version,
  pollIntervalMs: 500,
  timeoutMs: 60000,
});
if (explanation.status === "failed") {
  console.error(explanation.error);
}
```

다른 빌드 도구나 Node에서는 `createAmlClient`에 환경변수 네 개를 직접 전달하면 됩니다. React 등을 설치할 필요는 없습니다. 전체 조사 화면 흐름은 `demo.js`에 있습니다.

실제 모델 서비스로 전환할 때는 동일한 HTTP 경로·요청·응답 계약을 제공한 뒤 해당 Base URL 환경변수만 바꿉니다. 프론트엔드 함수 호출과 거래 ID 연결은 그대로 사용합니다. 서버별 CORS에는 실제 프론트엔드 Origin을 설정해야 합니다.

`waitForExplanation`은 `pending`을 반복 조회하고 `completed` 또는 `failed` 결과를 반환합니다. `not_requested`이면 먼저 POST가 필요하다는 오류를 냅니다. 제한 시간이나 전달한 AbortSignal에 도달하면 중단하므로 실제 모델이 느려져도 요청이 무한히 이어지지 않습니다. 요청 함수들은 `{ signal }`을 지원합니다. HTTP 오류는 `AmlApiError`의 `status`, `code`, `details`, `service`로 구분할 수 있습니다.

검증은 프로젝트 루트에서 `node --test examples/frontend/client.test.mjs` 또는 `python -m pytest tests/test_frontend_client.py -q`로 실행합니다. 네트워크·npm 의존성 없이 실제 Fetch 요청 URL과 상태 처리를 검사합니다.
