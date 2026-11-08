"""Explanation job submission and results. Default: http://localhost:8003."""
from app.factory import create_app

app = create_app(service="explanation")
