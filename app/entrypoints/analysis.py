"""Typology analysis only. Default address: http://localhost:8004."""
from app.factory import create_app

app = create_app(service="analysis")
