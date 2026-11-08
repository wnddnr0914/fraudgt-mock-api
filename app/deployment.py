"""Public service boundaries; each entrypoint runs as its own Uvicorn process."""
from dataclasses import dataclass
from typing import Literal

ServiceName = Literal["alerts", "graph", "explanation", "analysis"]


@dataclass(frozen=True)
class ServiceSpec:
    name: ServiceName
    title: str
    module: str
    port: int

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.port}"


SERVICE_SPECS: dict[str, ServiceSpec] = {
    "alerts": ServiceSpec("alerts", "Alert Query API", "app.entrypoints.alerts:app", 8001),
    "graph": ServiceSpec("graph", "Subgraph API", "app.entrypoints.graph:app", 8002),
    "explanation": ServiceSpec("explanation", "Explanation API", "app.entrypoints.explanation:app", 8003),
    "analysis": ServiceSpec("analysis", "Typology Analysis API", "app.entrypoints.analysis:app", 8004),
}
