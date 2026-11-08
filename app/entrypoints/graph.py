"""Directed subgraph only. Default address: http://localhost:8002."""
from app.factory import create_app

app = create_app(service="graph")
