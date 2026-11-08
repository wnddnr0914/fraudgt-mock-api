"""Public contract checks for independently deployable service applications."""
from contextlib import ExitStack
from importlib import import_module

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.factory import create_app


ROUTES = {
    "alerts": {("/api/alerts", "get"), ("/api/alerts/{transaction_id}", "get")},
    "graph": {("/api/alerts/{transaction_id}/graph", "get")},
    "explanation": {("/api/alerts/{transaction_id}/explanation", "post"),
                    ("/api/alerts/{transaction_id}/explanation", "get")},
    "analysis": {("/api/alerts/{transaction_id}/analysis", "get")},
}
BASE_URLS = {service: f"http://localhost:{8001 + index}" for index, service in enumerate(ROUTES)}
TARGET = "/api/alerts/TX000003"
PERIOD = {"start": "2022-11-01T00:00:00Z", "end": "2022-11-02T00:00:00Z"}


def operations(schema):
    return {(path, method) for path, item in schema["paths"].items()
            for method in item if method in {"get", "post", "put", "patch", "delete"}}


@pytest.mark.parametrize("service", ROUTES)
def test_service_documents_only_its_own_endpoints_and_allows_frontend(service):
    with TestClient(create_app(settings=Settings(), service=service), base_url=BASE_URLS[service]) as client:
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()
        assert operations(schema) == ROUTES[service]
        path, method = next(iter(ROUTES[service]))
        preflight = client.options(path.replace("{transaction_id}", "TX000003"), headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": method.upper(),
            "Access-Control-Request-Headers": "content-type",
        })
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.parametrize("service", ROUTES)
def test_service_does_not_proxy_routes_owned_by_another_service(service):
    with TestClient(create_app(settings=Settings(), service=service)) as client:
        for other, routes in ROUTES.items():
            if other == service:
                continue
            for path, method in routes:
                response = client.request(method, path.replace("{transaction_id}", "TX000003"),
                                          params=PERIOD if path == "/api/alerts" else {})
                assert response.status_code == 404, (service, other, path, response.text)


@pytest.mark.parametrize("service", ROUTES)
def test_dedicated_uvicorn_entrypoint_owns_the_same_public_contract(service):
    module = import_module(f"app.entrypoints.{service}")
    assert operations(module.app.openapi()) == ROUTES[service]


def test_split_services_preserve_the_six_existing_json_contracts():
    calls = [
        ("alerts", "GET", "/api/alerts", {"params": PERIOD}),
        ("alerts", "GET", TARGET, {}),
        ("graph", "GET", TARGET + "/graph", {"params": {"hops": 2, "lookback_days": 7}}),
        ("explanation", "GET", TARGET + "/explanation", {}),
        ("explanation", "POST", TARGET + "/explanation", {"json": {"model_version": "fraudgt-mock-v1"}}),
        ("explanation", "GET", TARGET + "/explanation", {}),
        ("analysis", "GET", TARGET + "/analysis", {}),
    ]
    with ExitStack() as stack:
        combined = stack.enter_context(TestClient(create_app(settings=Settings(), service="all")))
        clients = {name: stack.enter_context(TestClient(create_app(settings=Settings(), service=name), base_url=url))
                   for name, url in BASE_URLS.items()}
        for service, method, path, options in calls:
            before = combined.request(method, path, **options)
            after = clients[service].request(method, path, **options)
            assert after.status_code == before.status_code
            assert after.json() == before.json(), (service, method, path)


def test_independent_apps_share_transaction_ids_without_http_calls_between_services():
    with ExitStack() as stack:
        clients = {name: stack.enter_context(TestClient(create_app(settings=Settings(), service=name), base_url=url))
                   for name, url in BASE_URLS.items()}
        detail = clients["alerts"].get(TARGET).json()
        graph = clients["graph"].get(TARGET + "/graph").json()["graph"]
        posted = clients["explanation"].post(TARGET + "/explanation")
        result = clients["explanation"].get(TARGET + "/explanation").json()
        analysis = clients["analysis"].get(TARGET + "/analysis").json()
        edge_ids = {edge["id"] for edge in graph["edges"]}
        assert posted.status_code == 202 and result["status"] == "completed"
        assert posted.json()["explanation_id"] == result["explanation_id"]
        assert detail["transaction_id"] == analysis["transaction_id"] == result["transaction_id"]
        assert detail["fraud_score"] == analysis["fraud_score"]
        assert set(analysis["evidence"]["related_transaction_ids"]) <= edge_ids
        assert {edge["transaction_id"] for edge in result["edge_importance"]} <= edge_ids
        assert clients["explanation"].post(TARGET + "/explanation").json()["explanation_id"] == result["explanation_id"]
        failed = "/api/alerts/TX000018/explanation"
        assert clients["explanation"].post(failed).status_code == 202
        assert clients["explanation"].get(failed).json()["status"] == "failed"


def test_explanation_job_storage_is_local_to_the_explanation_app_instance():
    # The shipped Mock uses one process per service. Shared DB/job storage is a
    # documented prerequisite before scaling the explanation service itself.
    with TestClient(create_app(Settings(), service="explanation")) as first:
        first.post(TARGET + "/explanation")
        assert first.get(TARGET + "/explanation").json()["status"] == "completed"
    with TestClient(create_app(Settings(), service="explanation")) as restarted:
        assert restarted.get(TARGET + "/explanation").json()["status"] == "not_requested"
