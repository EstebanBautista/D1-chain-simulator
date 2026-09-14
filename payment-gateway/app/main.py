"""Payment gateway application entry point.

Assembly only: configure logging, create the schema, create the application
and register every blueprint the service exposes.
"""

from flask import Flask

# Imported so SQLAlchemy registers the model on the metadata before the tables
# are created. `core/` cannot do this itself — nothing in core may import a
# domain package — so the entry point does it.
from app.charges import models  # noqa: F401
from app.charges.router import blueprint as charges_blueprint
from app.core.database import create_tables
from app.core.logging import configure_logging

configure_logging()


def create_app() -> Flask:
    """Assemble the Flask application."""
    app = Flask(__name__)
    create_tables()
    app.register_blueprint(charges_blueprint)
    return app


app = create_app()
