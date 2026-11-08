from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


PERIOD = {"start": "2022-11-01T00:00:00Z", "end": "2022-11-02T00:00:00Z"}
ALL_TIME = {"start": "2022-10-01T00:00:00Z", "end": "2022-12-01T00:00:00Z"}
TARGET = "TX000003"
BASE = f"/api/alerts/{TARGET}"


def ids(response):
    return {edge["id"] for edge in response.json()["graph"]["edges"]}


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_period_filters_and_newest_first(client):
    response = client.get("/api/alerts", params=PERIOD)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    assert body["page"] == 1 and body["page_size"] == 20
    timestamps = [dt(alert["timestamp"]) for alert in body["alerts"]]
    assert all(dt(PERIOD["start"]) <= time < dt(PERIOD["end"]) for time in timestamps)
    assert timestamps == sorted(timestamps, reverse=True)
    assert all(alert["fraud_score"] >= 0.8 and alert["is_alert"] for alert in body["alerts"])


def test_different_periods_have_different_alerts(client):
    first = client.get("/api/alerts", params=PERIOD).json()
    second = client.get("/api/alerts", params={"start": "2022-11-02T00:00:00Z", "end": "2022-11-04T00:00:00Z"}).json()
    assert first["total"] and second["total"]
    assert {item["transaction_id"] for item in first["alerts"]}.isdisjoint(
        item["transaction_id"] for item in second["alerts"]
    )


def test_period_is_start_inclusive_end_exclusive(client):
    start = "2022-11-01T10:07:00Z"
    end = "2022-11-01T10:07:01Z"
    selected = client.get("/api/alerts", params={"start": start, "end": end}).json()
    assert TARGET in {item["transaction_id"] for item in selected["alerts"]}
    excluded = client.get("/api/alerts", params={"start": "2022-11-01T10:06:59Z", "end": start}).json()
    assert TARGET not in {item["transaction_id"] for item in excluded["alerts"]}


def test_equivalent_timezone_offsets(client):
    utc = client.get("/api/alerts", params=PERIOD).json()
    seoul = client.get("/api/alerts", params={"start": "2022-11-01T09:00:00+09:00", "end": "2022-11-02T09:00:00+09:00"}).json()
    assert utc == seoul


def test_pagination_counts_complete_result(client):
    params = {**ALL_TIME, "page_size": 2}
    one = client.get("/api/alerts", params={**params, "page": 1}).json()
    two = client.get("/api/alerts", params={**params, "page": 2}).json()
    assert one["total"] == two["total"] > 2
    assert len(one["alerts"]) == len(two["alerts"]) == 2
    assert {item["transaction_id"] for item in one["alerts"]}.isdisjoint(
        item["transaction_id"] for item in two["alerts"]
    )
    past_end = client.get("/api/alerts", params={**params, "page": 1000}).json()
    assert past_end["total"] == one["total"] and past_end["alerts"] == []


def test_score_filter_and_threshold_floor(client):
    normal = client.get("/api/alerts", params={**ALL_TIME, "page_size": 100}).json()
    low = client.get("/api/alerts", params={**ALL_TIME, "page_size": 100, "min_score": 0}).json()
    strict = client.get("/api/alerts", params={**ALL_TIME, "page_size": 100, "min_score": 0.9}).json()
    assert normal == low
    assert 0 < strict["total"] < normal["total"]
    assert all(item["fraud_score"] >= 0.9 for item in strict["alerts"])


def test_empty_period(client):
    result = client.get("/api/alerts", params={"start": "2030-01-01T00:00:00Z", "end": "2030-01-02T00:00:00Z"})
    assert result.status_code == 200
    assert result.json()["total"] == 0 and result.json()["alerts"] == []


@pytest.mark.parametrize("suffix", ["", "/graph", "/explanation", "/analysis"])
def test_unknown_transaction_is_404(client, suffix):
    result = client.get(f"/api/alerts/DOES_NOT_EXIST{suffix}")
    assert result.status_code == 404
    assert result.json()["error"]["code"]


@pytest.mark.parametrize("suffix", ["", "/graph", "/explanation", "/analysis"])
def test_known_non_alert_is_404(client, suffix):
    assert client.get(f"/api/alerts/TX000001{suffix}").status_code == 404


def test_configured_threshold_changes_visibility():
    with TestClient(create_app(settings=Settings(alert_threshold=0.95))) as client:
        assert client.get(BASE).status_code == 404
        listed = client.get("/api/alerts", params=ALL_TIME).json()
        assert listed["total"] > 0
        assert all(item["fraud_score"] >= 0.95 for item in listed["alerts"])


@pytest.mark.parametrize("start,end", [("2022-11-02T00:00:00Z", "2022-11-01T00:00:00Z"), ("2022-11-01T00:00:00Z", "2022-11-01T00:00:00Z")])
def test_reversed_or_empty_period_is_400(client, start, end):
    response = client.get("/api/alerts", params={"start": start, "end": end})
    assert response.status_code == 400
    assert response.json()["error"]["code"]


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"min_score": -0.01}, {"min_score": 1.01}, {"min_score": "NaN"}, {"start": "not-a-date"}, {"start": "2022-11-01T00:00:00"}, {"start": "1667296800"}])
def test_invalid_list_parameters_are_422(client, params):
    response = client.get("/api/alerts", params={**PERIOD, **params})
    assert response.status_code == 422
    assert response.json()["error"]["details"]


def test_detail_matches_list_and_versions(client):
    detail = client.get(BASE)
    assert detail.status_code == 200
    result = detail.json()
    assert result["transaction_id"] == TARGET
    assert result["sender_account"] == "B" and result["receiver_account"] == "D"
    assert result["fraud_score"] == 0.81
    assert result["model_version"] == "fraudgt-mock-v1"
    listed = next(item for item in client.get("/api/alerts", params=PERIOD).json()["alerts"] if item["transaction_id"] == TARGET)
    assert all(result[key] == value for key, value in listed.items())
    assert "Is_laundering" not in result and "Laundering_type" not in result


def test_graph_contains_target_and_preserves_direction(client):
    response = client.get(f"{BASE}/graph")
    assert response.status_code == 200
    graph = response.json()["graph"]
    target = [edge for edge in graph["edges"] if edge["is_target"]]
    assert len(target) == 1 and target[0]["id"] == TARGET
    assert target[0]["source"] == "B" and target[0]["target"] == "D"
    node_ids = [node["id"] for node in graph["nodes"]]
    edge_ids = [edge["id"] for edge in graph["edges"]]
    assert len(node_ids) == len(set(node_ids)) and len(edge_ids) == len(set(edge_ids))
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"])
    assert all("importance" not in edge for edge in graph["edges"])


def test_one_hop_and_two_hops_differ(client):
    one = client.get(f"{BASE}/graph", params={"hops": 1})
    two = client.get(f"{BASE}/graph", params={"hops": 2})
    assert ids(one) < ids(two)


def test_lookback_window_changes_graph(client):
    short = client.get(f"{BASE}/graph", params={"lookback_days": 1})
    long = client.get(f"{BASE}/graph", params={"lookback_days": 7})
    assert ids(short) < ids(long)


def test_graph_never_includes_future_or_outside_window(client):
    graph = client.get(f"{BASE}/graph", params={"hops": 3, "lookback_days": 7}).json()["graph"]
    target_time = dt(client.get(BASE).json()["timestamp"])
    assert all(target_time - timedelta(days=7) <= dt(edge["timestamp"]) <= target_time for edge in graph["edges"])
    edge_ids = {edge["id"] for edge in graph["edges"]}
    assert "TX000030" in edge_ids  # Exactly seven days ago: inclusive lower bound.
    assert "TX000010" not in edge_ids and "TX000031" not in edge_ids


def test_parallel_edges_are_preserved(client):
    graph = client.get(f"{BASE}/graph").json()["graph"]
    parallel = [edge for edge in graph["edges"] if edge["source"] == "A" and edge["target"] == "B"]
    assert len(parallel) >= 2
    assert len({edge["id"] for edge in parallel}) == len(parallel)


def test_graph_edge_ids_and_endpoints_match_common_repository(client):
    transactions = {item.transaction_id: item for item in client.app.state.repository.transactions()}
    assert len(transactions) >= 20
    graph = client.get(f"{BASE}/graph").json()["graph"]
    for edge in graph["edges"]:
        original = transactions[edge["id"]]
        assert edge["source"] == original.sender_account
        assert edge["target"] == original.receiver_account
        assert edge["amount"] == original.amount
        assert edge["currency"] == original.payment_currency
        assert dt(edge["timestamp"]) == original.timestamp


@pytest.mark.parametrize("params", [{"hops": 0}, {"hops": 4}, {"lookback_days": 0}, {"lookback_days": 31}])
def test_invalid_graph_parameters_are_422(client, params):
    assert client.get(f"{BASE}/graph", params=params).status_code == 422


def test_explanation_lifecycle_and_idempotency(client):
    before = client.get(f"{BASE}/explanation")
    assert before.status_code == 200 and before.json()["status"] == "not_requested"
    request = {"model_version": "fraudgt-mock-v1"}
    first = client.post(f"{BASE}/explanation", json=request)
    repeated = client.post(f"{BASE}/explanation", json=request)
    assert first.status_code == repeated.status_code == 202
    assert first.json() == repeated.json()
    assert first.json()["status"] == "pending"
    completed = client.get(f"{BASE}/explanation")
    body = completed.json()
    assert completed.status_code == 200 and body["status"] == "completed"
    assert body["explanation_id"] == first.json()["explanation_id"]
    assert body["method"] == "GNNExplainer"
    assert body["model_version"] == "fraudgt-mock-v1"
    assert body["edge_importance"]
    graph_ids = ids(client.get(f"{BASE}/graph"))
    assert all(0 <= edge["importance"] <= 1 and edge["transaction_id"] in graph_ids for edge in body["edge_importance"])
    assert TARGET not in {edge["transaction_id"] for edge in body["edge_importance"]}
    assert client.get(f"{BASE}/explanation").json() == body
    assert client.post(f"{BASE}/explanation", json=request).json()["explanation_id"] == body["explanation_id"]


def test_explanation_without_body_uses_default_version(client):
    result = client.post(f"{BASE}/explanation")
    assert result.status_code == 202
    assert result.json()["model_version"] == "fraudgt-mock-v1"


def test_explanation_snapshot_is_independent_of_display_parameters(client):
    client.post(f"{BASE}/explanation")
    result = client.get(f"{BASE}/explanation").json()
    snapshot = result["graph_snapshot"]
    assert snapshot["graph_id"] and snapshot["preprocessing_version"] and snapshot["sampler"]
    assert snapshot["model_version"] == result["model_version"]
    assert snapshot["transaction_id"] == TARGET
    assert TARGET in snapshot["edge_transaction_ids"]
    assert {edge["transaction_id"] for edge in result["edge_importance"]} <= set(snapshot["edge_transaction_ids"])
    client.get(f"{BASE}/graph", params={"hops": 1, "lookback_days": 1})
    assert client.get(f"{BASE}/explanation").json()["graph_snapshot"] == snapshot


def test_failed_explanation_is_a_normal_job_state(client):
    endpoint = "/api/alerts/TX000018/explanation"
    assert client.get(endpoint).json()["status"] == "not_requested"
    created = client.post(endpoint)
    assert created.status_code == 202 and created.json()["status"] == "pending"
    result = client.get(endpoint)
    assert result.status_code == 200 and result.json()["status"] == "failed"
    assert result.json()["edge_importance"] == [] and result.json()["error"]["code"]
    assert client.get(endpoint).json() == result.json()


def test_unavailable_analysis_is_explicit_null(client):
    response = client.get("/api/alerts/TX000017/analysis")
    assert response.status_code == 200
    assert response.json()["typology"] is None and response.json()["evidence"] is None
    detail = client.get("/api/alerts/TX000017").json()
    assert detail["predicted_typology"] is None and detail["typology_confidence"] is None


def test_unsupported_explanation_version(client):
    assert client.post(f"{BASE}/explanation", json={"model_version": "unknown-v999"}).status_code == 409
    assert client.get(f"{BASE}/explanation", params={"model_version": "unknown-v999"}).status_code == 409


def test_unknown_request_body_fields_are_422(client):
    assert client.post(f"{BASE}/explanation", json={"model_version": "fraudgt-mock-v1", "run_real_model": True}).status_code == 422


def test_analysis_structure_and_directed_path(client):
    response = client.get(f"{BASE}/analysis")
    assert response.status_code == 200
    analysis = response.json()
    assert analysis["transaction_id"] == TARGET and analysis["fraud_score"] == 0.81
    assert analysis["typology"]["verification_status"] == "unverified"
    assert analysis["typology"]["model_version"] == "typology-mock-v1"
    assert 0 <= analysis["typology"]["confidence"] <= 1
    evidence = analysis["evidence"]
    graph = client.get(f"{BASE}/graph").json()["graph"]
    graph_edges = {edge["id"]: edge for edge in graph["edges"]}
    assert set(evidence["related_transaction_ids"]) <= graph_edges.keys()
    assert TARGET in evidence["related_transaction_ids"]
    for source, target in zip(evidence["account_path"], evidence["account_path"][1:]):
        assert any(edge["source"] == source and edge["target"] == target for edge in graph_edges.values())
    assert evidence["description"]


def test_all_analysis_references_match_existing_directed_transactions(client):
    transactions = {item.transaction_id: item for item in client.app.state.repository.transactions()}
    alerts = client.get("/api/alerts", params={**ALL_TIME, "page_size": 100}).json()["alerts"]
    for alert in alerts:
        analysis = client.get(f"/api/alerts/{alert['transaction_id']}/analysis").json()
        evidence = analysis["evidence"]
        if evidence is None:
            assert analysis["typology"] is None
            continue
        related = [transactions[tx_id] for tx_id in evidence["related_transaction_ids"]]
        assert all(item.timestamp <= dt(alert["timestamp"]) for item in related)
        links = {(item.sender_account, item.receiver_account) for item in related}
        assert all(pair in links for pair in zip(evidence["account_path"], evidence["account_path"][1:]))


def test_repeated_read_calls_are_stable(client):
    for endpoint, params in [("/api/alerts", PERIOD), (BASE, {}), (f"{BASE}/graph", {}), (f"{BASE}/analysis", {})]:
        assert client.get(endpoint, params=params).json() == client.get(endpoint, params=params).json()


def test_cors_preflight(client):
    response = client.options(f"{BASE}/explanation", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.options(BASE, headers={"Origin": "https://unknown.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in denied.headers


def test_docs_and_six_documented_operations(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    operations = [(path, method) for path, item in paths.items() for method in item if method in {"get", "post", "put", "delete", "patch"}]
    assert len(operations) == 6
    assert all(path.startswith("/api/") for path, _ in operations)
    for path, method in operations:
        operation = paths[path][method]
        assert operation.get("summary") and operation.get("description")
        assert "422" in operation["responses"] and "500" in operation["responses"]


def test_internal_error_response_is_safe():
    app = create_app(settings=Settings())
    with TestClient(app, raise_server_exceptions=False) as client:
        def broken(*args, **kwargs):
            raise RuntimeError("secret database credentials")

        app.state.services.alerts.get_alert = broken
        response = client.get(BASE)
        assert response.status_code == 500
        assert response.json()["error"]["code"]
        assert "secret" not in response.text
