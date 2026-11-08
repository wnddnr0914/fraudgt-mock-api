"""Optional combined compatibility app. New integrations use app.entrypoints.*."""
from app.factory import create_app

app = create_app()
