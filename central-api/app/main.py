"""Central API application entry point.

Assembly only: configure logging, create the application, and include every
router the service exposes. No route is registered anywhere else, so this file
is the complete list of what head office serves.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import configure_logging
from app.core.router import router as health_router
from app.ingestion.router import router as ingestion_router
from app.reports.router import router as reports_router
from app.stores.router import router as stores_router

configure_logging()

app = FastAPI(
    title="D1 Central API",
    description="Consolidated sales for the chain: ingestion and reporting",
    version="1.0.0",
)

# The dashboard reaches this through its own nginx proxy, so it is same-origin
# in practice. CORS stays open anyway because the API is also reachable
# directly for `curl` and for /docs. Wide open on purpose: this is a local
# practice environment, not a deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(stores_router)
app.include_router(ingestion_router)
app.include_router(reports_router)
