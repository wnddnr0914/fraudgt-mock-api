"""Check four independently running Mock APIs using the Python standard library."""
import argparse
import json
import os
import math
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SERVICE_DEFAULTS = {
    "alerts": "http://localhost:8001",
    "graph": "http://localhost:8002",
    "explanation": "http://localhost:8003",
    "analysis": "http://localhost:8004",
}
ROUTES = {
    "alerts": {("/api/alerts", "get"), ("/api/alerts/{transaction_id}", "get")},
    "graph": {("/api/alerts/{transaction_id}/graph", "get")},
    "explanation": {("/api/alerts/{transaction_id}/explanation", "post"),
                    ("/api/alerts/{transaction_id}/explanation", "get")},
    "analysis": {("/api/alerts/{transaction_id}/analysis", "get")},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for service, default in SERVICE_DEFAULTS.items():
        parser.add_argument(f"--{service}-base-url", default=os.getenv(f"{service.upper()}_BASE_URL", default),
                            help=f"{service} origin; default %(default)s")
    parser.add_argument("--base-url", help="Explicit compatibility mode: check the legacy combined app at this URL")
    parser.add_argument("--origin", default="http://localhost:5173", help="Frontend Origin expected in CORS responses")
    parser.add_argument("--timeout", type=float, default=10, help="HTTP timeout in seconds; use 120 for Render Free after warming services")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a positive finite number")
    base_urls = {name: (args.base_url or getattr(args, f"{name}_base_url")).rstrip("/")
                 for name in SERVICE_DEFAULTS}
    checked = []

    def call(service, method, path, expected=200, body=None, headers=None):
        request_headers = {"Origin": args.origin, **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        url = base_urls[service] + path
        request = Request(url, method=method, headers=request_headers, data=data)
        with urlopen(request, timeout=args.timeout) as response:
            assert response.status == expected, (url, response.status)
            assert response.headers.get("Access-Control-Allow-Origin") == request_headers["Origin"], url
            content = response.read()
            checked.append(f"[{service}] {method} {url}: {response.status}")
            if response.headers.get_content_type() == "application/json":
                return json.loads(content)
            return content

    period = urlencode({"start": "2022-11-01T00:00:00Z", "end": "2022-11-02T00:00:00Z"})
    listed = call("alerts", "GET", "/api/alerts?" + period)
    assert listed["total"] > 0
    target = "/api/alerts/TX000003"
    detail = call("alerts", "GET", target)
    assert detail["transaction_id"] == "TX000003"
    graph = call("graph", "GET", target + "/graph?hops=2&lookback_days=7")["graph"]
    graph_ids = {edge["id"] for edge in graph["edges"]}
    assert "TX000003" in graph_ids and all("importance" not in edge for edge in graph["edges"])
    requested = call("explanation", "POST", target + "/explanation", expected=202,
                     body={"model_version": "fraudgt-mock-v1"})
    explained = call("explanation", "GET", target + "/explanation")
    assert explained["status"] == "completed"
    assert requested["explanation_id"] == explained["explanation_id"]
    assert all(edge["transaction_id"] in graph_ids and 0 <= edge["importance"] <= 1
               for edge in explained["edge_importance"])
    analysis = call("analysis", "GET", target + "/analysis")
    assert analysis["fraud_score"] == detail["fraud_score"]
    assert set(analysis["evidence"]["related_transaction_ids"]) <= graph_ids

    all_routes = set().union(*ROUTES.values())
    for service, expected_routes in ROUTES.items():
        assert b"swagger" in call(service, "GET", "/docs").lower()
        schema = call(service, "GET", "/openapi.json")
        actual = {(path, method) for path, operations in schema["paths"].items()
                  for method in operations if method in {"get", "post", "put", "patch", "delete"}}
        assert actual == (all_routes if args.base_url else expected_routes), (service, actual)
        for path, method in actual:
            status = "202" if method == "post" else "200"
            assert schema["paths"][path][method]["responses"][status]["content"]["application/json"]["examples"]["fixture"]["value"]
        endpoint, verb = next(iter(expected_routes))
        call(service, "OPTIONS", endpoint.replace("{transaction_id}", "TX000003"), headers={
            "Access-Control-Request-Method": verb.upper(),
            "Access-Control-Request-Headers": "content-type",
        })
    print("\n".join(checked))
    print("PASS: six API operations across four Base URLs, service-specific Swagger/OpenAPI, CORS and shared transaction IDs")


if __name__ == "__main__":
    main()
