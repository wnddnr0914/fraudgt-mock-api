"""Alert list and detail only. Default address: http://localhost:8001."""
from app.factory import create_app

app = create_app(service="alerts")
