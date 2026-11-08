"""Cross-cutting version-selection and duplicate-submission guarantees."""
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_unavailable_selected_typology_version_hides_stale_output():
    # Selecting a future model must not silently serve a prior model's result.
    with TestClient(create_app(Settings(typology_model_version="typology-v2-not-loaded"))) as client:
        detail = client.get("/api/alerts/TX000003").json()
        analysis = client.get("/api/alerts/TX000003/analysis").json()
        assert detail["fraud_score"] == analysis["fraud_score"] == 0.81
        assert detail["predicted_typology"] is None
        assert detail["typology_confidence"] is None
        assert detail["typology_model_version"] is None
        assert analysis["typology"] is None and analysis["evidence"] is None


def test_concurrent_duplicate_explanation_submissions_share_one_job():
    # Independent requests can reach multiple sync route threads at once.
    with TestClient(create_app(Settings())) as client:
        endpoint = "/api/alerts/TX000003/explanation"

        def submit(_):
            response = client.post(endpoint, json={"model_version": "fraudgt-mock-v1"})
            assert response.status_code == 202
            return response.json()

        with ThreadPoolExecutor(max_workers=8) as executor:
            submissions = list(executor.map(submit, range(24)))
        assert len({row["explanation_id"] for row in submissions}) == 1
        assert {row["status"] for row in submissions} == {"pending"}
        result = client.get(endpoint).json()
        assert result["status"] == "completed"
        assert result["explanation_id"] == submissions[0]["explanation_id"]


def test_every_prepared_snapshot_maps_to_its_default_display_graph():
    # This is a Mock fixture guarantee, not an assumption about future sampled
    # FraudGT input graphs. It catches stale snapshot IDs after fixture edits.
    app = create_app(Settings())
    repository = app.state.repository
    checked = 0
    for transaction in repository.transactions():
        fixture = repository.get_explanation_fixture(transaction.transaction_id, "fraudgt-mock-v1")
        if fixture is None:
            continue
        graph = app.state.services.graphs.get_graph(transaction.transaction_id).graph
        assert set(fixture.snapshot.edge_transaction_ids) <= {edge.id for edge in graph.edges}
        assert {item.transaction_id for item in fixture.edge_importance} <= {edge.id for edge in graph.edges}
        checked += 1
    assert checked > 1
