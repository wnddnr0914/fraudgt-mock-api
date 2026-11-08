# 서비스별 API 요청·응답 예시

`python scripts/export_contract.py`가 각 서비스의 실제 TestClient 응답에서 생성한 문서입니다.

서비스는 각각의 Base URL로 직접 호출합니다. 경로와 요청·응답 JSON은 기존 6개 API 계약을 유지합니다.

| 서비스 | 기본 Base URL | OpenAPI 계약 |
|---|---|---|
| alerts | `http://localhost:8001` | [JSON](../openapi/alerts.json) |
| graph | `http://localhost:8002` | [JSON](../openapi/graph.json) |
| explanation | `http://localhost:8003` | [JSON](../openapi/explanation.json) |
| analysis | `http://localhost:8004` | [JSON](../openapi/analysis.json) |

프론트엔드는 `examples/frontend/.env.example`의 서비스별 Vite 환경변수와 재사용 클라이언트를 사용합니다. 실제 모델 서버로 교체할 때는 해당 서비스 주소 설정을 바꾸고 같은 메서드·경로·JSON·작업 상태 계약을 유지합니다.

`openapi.json`은 기존 단일 서버의 호환용 계약입니다. 기본 실행은 서비스별 독립 서버 4개입니다. 중요도와 예측은 모두 고정 Mock 출력이며 실제 모델 계산 결과가 아닙니다.

## 기간별 이상거래 목록

서비스: `alerts`

```http
GET http://localhost:8001/api/alerts?start=2022-11-01T00%3A00%3A00Z&end=2022-11-02T00%3A00%3A00Z
```

응답 HTTP 200:

```json
{
  "total": 7,
  "page": 1,
  "page_size": 20,
  "alerts": [
    {
      "transaction_id": "TX000006",
      "timestamp": "2022-11-01T10:15:00Z",
      "sender_account": "F",
      "receiver_account": "D",
      "amount": 2500.0,
      "currency": "USD",
      "fraud_score": 0.95,
      "is_alert": true,
      "model_version": "fraudgt-mock-v1",
      "predicted_typology": "Cycle",
      "typology_confidence": 0.78,
      "typology_model_version": "typology-mock-v1",
      "status": "unreviewed"
    },
    {
      "transaction_id": "TX000005",
      "timestamp": "2022-11-01T10:12:00Z",
      "sender_account": "E",
      "receiver_account": "F",
      "amount": 2600.0,
      "currency": "USD",
      "fraud_score": 0.93,
      "is_alert": true,
      "model_version": "fraudgt-mock-v1",
      "predicted_typology": null,
      "typology_confidence": null,
      "typology_model_version": null,
      "status": "unreviewed"
    },
    {
      "transaction_id": "TX000004",
      "timestamp": "2022-11-01T10:10:00Z",
      "sender_account": "D",
      "receiver_account": "E",
      "amount": 2700.0,
      "currency": "USD",
      "fraud_score": 0.9,
      "is_alert": true,
      "model_version": "fraudgt-mock-v1",
      "predicted_typology": null,
      "typology_confidence": null,
      "typology_model_version": null,
      "status": "unreviewed"
    },
    {
      "transaction_id": "TX000003",
      "timestamp": "2022-11-01T10:07:00Z",
      "sender_account": "B",
      "receiver_account": "D",
      "amount": 2800.0,
      "currency": "USD",
      "fraud_score": 0.81,
      "is_alert": true,
      "model_version": "fraudgt-mock-v1",
      "predicted_typology": "Layering",
      "typology_confidence": 0.72,
      "typology_model_version": "typology-mock-v1",
      "status": "unreviewed"
    },
    {
      "transaction_id": "TX000013",
      "timestamp": "2022-11-01T10:06:30Z",
      "sender_account": "B",
      "receiver_account": "J",
      "amount": 350.0,
      "currency": "USD",
      "fraud_score": 0.87,
      "is_alert": true,
      "model_version": "fraudgt-mock-v1",
      "predicted_typology": "Fan-Out",
      "typology_confidence": 0.78,
      "typology_model_version": "typology-mock-v1",
      "status": "unreviewed"
    },
    {
      "transaction_id": "TX000012",
      "timestamp": "2022-11-01T10:06:00Z",
      "sender_account": "B",
      "receiver_account": "I",
      "amount": 400.0,
      "currency": "USD",
      "fraud_score": 0.86,
      "is_alert": true,
      "model_version": "fraudgt-mock-v1",
      "predicted_typology": "Fan-Out",
      "typology_confidence": 0.78,
      "typology_model_version": "typology-mock-v1",
      "status": "unreviewed"
    },
    {
      "transaction_id": "TX000002",
      "timestamp": "2022-11-01T10:03:00Z",
      "sender_account": "C",
      "receiver_account": "B",
      "amount": 2000.0,
      "currency": "USD",
      "fraud_score": 0.92,
      "is_alert": true,
      "model_version": "fraudgt-mock-v1",
      "predicted_typology": "Fan-In",
      "typology_confidence": 0.78,
      "typology_model_version": "typology-mock-v1",
      "status": "unreviewed"
    }
  ]
}
```

## 거래 상세

서비스: `alerts`

```http
GET http://localhost:8001/api/alerts/TX000003
```

응답 HTTP 200:

```json
{
  "transaction_id": "TX000003",
  "timestamp": "2022-11-01T10:07:00Z",
  "sender_account": "B",
  "receiver_account": "D",
  "amount": 2800.0,
  "currency": "USD",
  "fraud_score": 0.81,
  "is_alert": true,
  "model_version": "fraudgt-mock-v1",
  "predicted_typology": "Layering",
  "typology_confidence": 0.72,
  "typology_model_version": "typology-mock-v1",
  "status": "unreviewed"
}
```

## 주변 거래 그래프

서비스: `graph`

```http
GET http://localhost:8002/api/alerts/TX000003/graph?hops=2&lookback_days=7
```

응답 HTTP 200:

```json
{
  "transaction_id": "TX000003",
  "graph": {
    "hops": 2,
    "lookback_days": 7,
    "neighborhood_direction": "both",
    "window_start": "2022-10-25T10:07:00Z",
    "window_end": "2022-11-01T10:07:00Z",
    "nodes": [
      {
        "id": "A"
      },
      {
        "id": "B"
      },
      {
        "id": "BORDER"
      },
      {
        "id": "C"
      },
      {
        "id": "D"
      },
      {
        "id": "G"
      },
      {
        "id": "I"
      },
      {
        "id": "J"
      },
      {
        "id": "N"
      },
      {
        "id": "R"
      }
    ],
    "edges": [
      {
        "id": "TX000030",
        "source": "BORDER",
        "target": "B",
        "amount": 20.0,
        "currency": "USD",
        "timestamp": "2022-10-25T10:07:00Z",
        "is_target": false
      },
      {
        "id": "TX000015",
        "source": "R",
        "target": "N",
        "amount": 550.0,
        "currency": "USD",
        "timestamp": "2022-10-27T08:00:00Z",
        "is_target": false
      },
      {
        "id": "TX000014",
        "source": "N",
        "target": "B",
        "amount": 600.0,
        "currency": "USD",
        "timestamp": "2022-10-28T08:00:00Z",
        "is_target": false
      },
      {
        "id": "TX000008",
        "source": "G",
        "target": "A",
        "amount": 900.0,
        "currency": "USD",
        "timestamp": "2022-10-31T09:00:00Z",
        "is_target": false
      },
      {
        "id": "TX000001",
        "source": "A",
        "target": "B",
        "amount": 1000.0,
        "currency": "USD",
        "timestamp": "2022-11-01T10:01:00Z",
        "is_target": false
      },
      {
        "id": "TX000029",
        "source": "A",
        "target": "B",
        "amount": 1000.0,
        "currency": "USD",
        "timestamp": "2022-11-01T10:01:00Z",
        "is_target": false
      },
      {
        "id": "TX000007",
        "source": "A",
        "target": "B",
        "amount": 1000.0,
        "currency": "USD",
        "timestamp": "2022-11-01T10:02:00Z",
        "is_target": false
      },
      {
        "id": "TX000002",
        "source": "C",
        "target": "B",
        "amount": 2000.0,
        "currency": "USD",
        "timestamp": "2022-11-01T10:03:00Z",
        "is_target": false
      },
      {
        "id": "TX000012",
        "source": "B",
        "target": "I",
        "amount": 400.0,
        "currency": "USD",
        "timestamp": "2022-11-01T10:06:00Z",
        "is_target": false
      },
      {
        "id": "TX000013",
        "source": "B",
        "target": "J",
        "amount": 350.0,
        "currency": "USD",
        "timestamp": "2022-11-01T10:06:30Z",
        "is_target": false
      },
      {
        "id": "TX000003",
        "source": "B",
        "target": "D",
        "amount": 2800.0,
        "currency": "USD",
        "timestamp": "2022-11-01T10:07:00Z",
        "is_target": true
      }
    ]
  }
}
```

## 설명 요청 전 상태

서비스: `explanation`

```http
GET http://localhost:8003/api/alerts/TX000003/explanation
```

응답 HTTP 200:

```json
{
  "transaction_id": "TX000003",
  "explanation_id": null,
  "status": "not_requested",
  "method": "GNNExplainer",
  "model_version": "fraudgt-mock-v1",
  "graph_snapshot": null,
  "edge_importance": [],
  "error": null
}
```

## 설명 작업 요청

서비스: `explanation`

```http
POST http://localhost:8003/api/alerts/TX000003/explanation
```

요청 JSON:

```json
{
  "model_version": "fraudgt-mock-v1"
}
```

응답 HTTP 202:

```json
{
  "transaction_id": "TX000003",
  "explanation_id": "EXP-94270638dcd55fec44542f7b72cdacd7e6e55ebf3aaf70ef1418d3cfe1503e78",
  "status": "pending",
  "model_version": "fraudgt-mock-v1"
}
```

## 설명 결과

서비스: `explanation`

```http
GET http://localhost:8003/api/alerts/TX000003/explanation
```

응답 HTTP 200:

```json
{
  "transaction_id": "TX000003",
  "explanation_id": "EXP-94270638dcd55fec44542f7b72cdacd7e6e55ebf3aaf70ef1418d3cfe1503e78",
  "status": "completed",
  "method": "GNNExplainer",
  "model_version": "fraudgt-mock-v1",
  "graph_snapshot": {
    "graph_id": "SNAPSHOT-TX000003-v1",
    "transaction_id": "TX000003",
    "model_version": "fraudgt-mock-v1",
    "preprocessing_version": "samld-mock-preprocessing-v1",
    "sampler": "fixed-fixture-undirected-neighborhood",
    "seed": 42,
    "hops": 2,
    "lookback_days": 7,
    "edge_transaction_ids": [
      "TX000001",
      "TX000002",
      "TX000003",
      "TX000007",
      "TX000008",
      "TX000012",
      "TX000013",
      "TX000014",
      "TX000015",
      "TX000029",
      "TX000030"
    ],
    "node_account_ids": [
      "A",
      "B",
      "BORDER",
      "C",
      "D",
      "G",
      "I",
      "J",
      "N",
      "R"
    ]
  },
  "edge_importance": [
    {
      "transaction_id": "TX000001",
      "importance": 0.75
    },
    {
      "transaction_id": "TX000002",
      "importance": 0.86
    },
    {
      "transaction_id": "TX000007",
      "importance": 0.2
    },
    {
      "transaction_id": "TX000008",
      "importance": 0.3
    },
    {
      "transaction_id": "TX000012",
      "importance": 0.7
    },
    {
      "transaction_id": "TX000013",
      "importance": 0.8
    },
    {
      "transaction_id": "TX000014",
      "importance": 0.2
    },
    {
      "transaction_id": "TX000015",
      "importance": 0.3
    },
    {
      "transaction_id": "TX000029",
      "importance": 0.3
    },
    {
      "transaction_id": "TX000030",
      "importance": 0.4
    }
  ],
  "error": null
}
```

## 유형 분석

서비스: `analysis`

```http
GET http://localhost:8004/api/alerts/TX000003/analysis
```

응답 HTTP 200:

```json
{
  "transaction_id": "TX000003",
  "fraud_score": 0.81,
  "model_version": "fraudgt-mock-v1",
  "typology": {
    "predicted_type": "Layering",
    "confidence": 0.72,
    "verification_status": "unverified",
    "model_version": "typology-mock-v1"
  },
  "evidence": {
    "related_transaction_ids": [
      "TX000001",
      "TX000002",
      "TX000003"
    ],
    "account_path": [
      "A",
      "B",
      "D"
    ],
    "description": "B 계좌로 여러 거래가 유입된 뒤 D 계좌로 송금된 거래 흐름이 관찰됨."
  }
}
```

## 유형 분석 없음

서비스: `analysis`

```http
GET http://localhost:8004/api/alerts/TX000017/analysis
```

응답 HTTP 200:

```json
{
  "transaction_id": "TX000017",
  "fraud_score": 0.91,
  "model_version": "fraudgt-mock-v1",
  "typology": null,
  "evidence": null
}
```

## 없는 거래 오류

서비스: `alerts`

```http
GET http://localhost:8001/api/alerts/DOES_NOT_EXIST
```

응답 HTTP 404:

```json
{
  "error": {
    "code": "ALERT_NOT_FOUND",
    "message": "해당 거래가 없거나 현재 서버 임계값 이상의 Alert가 아닙니다.",
    "details": []
  }
}
```
