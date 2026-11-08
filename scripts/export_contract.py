"""Export fixture-derived examples and one OpenAPI contract per independent service."""
import json
import sys
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.config import Settings
from app.deployment import SERVICE_SPECS
from app.factory import create_app


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    calls = [
        ("기간별 이상거래 목록", "alerts", "GET", "/api/alerts?start=2022-11-01T00%3A00%3A00Z&end=2022-11-02T00%3A00%3A00Z", None, 200),
        ("거래 상세", "alerts", "GET", "/api/alerts/TX000003", None, 200),
        ("주변 거래 그래프", "graph", "GET", "/api/alerts/TX000003/graph?hops=2&lookback_days=7", None, 200),
        ("설명 요청 전 상태", "explanation", "GET", "/api/alerts/TX000003/explanation", None, 200),
        ("설명 작업 요청", "explanation", "POST", "/api/alerts/TX000003/explanation", {"model_version": "fraudgt-mock-v1"}, 202),
        ("설명 결과", "explanation", "GET", "/api/alerts/TX000003/explanation", None, 200),
        ("유형 분석", "analysis", "GET", "/api/alerts/TX000003/analysis", None, 200),
        ("유형 분석 없음", "analysis", "GET", "/api/alerts/TX000017/analysis", None, 200),
        ("없는 거래 오류", "alerts", "GET", "/api/alerts/DOES_NOT_EXIST", None, 404),
    ]
    examples = []
    with ExitStack() as stack:
        clients = {
            name: stack.enter_context(TestClient(create_app(settings=Settings(), service=name), base_url=spec.base_url))
            for name, spec in SERVICE_SPECS.items()
        }
        for title, service, method, url, body, expected in calls:
            response = clients[service].request(method, url, **({"json": body} if body is not None else {}))
            assert response.status_code == expected, (title, response.text)
            base_url = SERVICE_SPECS[service].base_url
            examples.append({
                "title": title, "service": service, "base_url": base_url,
                "method": method, "url": url, "request_url": base_url + url,
                "request_body": body, "status_code": response.status_code, "response": response.json(),
            })
        response_examples = {}
        for example in examples:
            if example["status_code"] not in {200, 202} or "TX000017" in example["url"]:
                continue
            path = example["url"].split("?", 1)[0].replace("/TX000003", "/{transaction_id}")
            response_examples.setdefault(path, {})[example["method"].lower()] = {
                str(example["status_code"]): {"summary": "합성 Fixture 응답", "value": example["response"]}
            }
        write_json(ROOT / "app" / "api" / "response_examples.json", response_examples)
        for name, client in clients.items():
            schema = client.get("/openapi.json").json()
            schema["servers"] = [{"url": SERVICE_SPECS[name].base_url, "description": "Local Mock service default"}]
            schema["x-service"] = name
            write_json(ROOT / "openapi" / f"{name}.json", schema)
        combined = stack.enter_context(TestClient(create_app(settings=Settings(), service="all")))
        compatibility_schema = combined.get("/openapi.json").json()
        compatibility_schema["servers"] = [{"url": "http://localhost:8000", "description": "Optional combined compatibility app"}]
        compatibility_schema["x-deployment-mode"] = "compatibility-combined"
        write_json(ROOT / "openapi.json", compatibility_schema)

    write_json(ROOT / "examples" / "api_examples.json", examples)
    lines = [
        "# 서비스별 API 요청·응답 예시", "",
        "`python scripts/export_contract.py`가 각 서비스의 실제 TestClient 응답에서 생성한 문서입니다.", "",
        "서비스는 각각의 Base URL로 직접 호출합니다. 경로와 요청·응답 JSON은 기존 6개 API 계약을 유지합니다.", "",
        "| 서비스 | 기본 Base URL | OpenAPI 계약 |", "|---|---|---|",
    ]
    for name, spec in SERVICE_SPECS.items():
        lines.append(f"| {name} | `{spec.base_url}` | [JSON](../openapi/{name}.json) |")
    lines.extend([
        "", "프론트엔드는 `examples/frontend/.env.example`의 서비스별 Vite 환경변수와 재사용 클라이언트를 사용합니다. "
        "실제 모델 서버로 교체할 때는 해당 서비스 주소 설정을 바꾸고 같은 메서드·경로·JSON·작업 상태 계약을 유지합니다.", "",
        "`openapi.json`은 기존 단일 서버의 호환용 계약입니다. 기본 실행은 서비스별 독립 서버 4개입니다. "
        "중요도와 예측은 모두 고정 Mock 출력이며 실제 모델 계산 결과가 아닙니다.", "",
    ])
    for example in examples:
        lines.extend([
            f"## {example['title']}", "", f"서비스: `{example['service']}`", "",
            "```http", f"{example['method']} {example['request_url']}", "```", "",
        ])
        if example["request_body"] is not None:
            lines.extend(["요청 JSON:", "", "```json", json.dumps(example["request_body"], ensure_ascii=False, indent=2), "```", ""])
        lines.extend([f"응답 HTTP {example['status_code']}:", "", "```json",
                      json.dumps(example["response"], ensure_ascii=False, indent=2), "```", ""])
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "API_EXAMPLES.md").write_text("\n".join(lines), encoding="utf-8")
    print("Exported four service OpenAPI files, compatibility contract, Swagger examples and service-specific request/response examples")


if __name__ == "__main__":
    main()
