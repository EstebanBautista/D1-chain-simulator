"""Backend application entry point.

Assembly only: configure logging, create the application, and include every
router the service exposes. No route is registered anywhere else, so this file
is the complete list of what the backend serves.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import configure_logging
from app.core.router import router as health_router
from app.payments.router import router as payments_router
from app.products.router import router as products_router
from app.sales.router import router as sales_router

configure_logging()

app = FastAPI(
    title="D1 Store Backend",
    description="Business logic and integrations for the simulated store",
    version="2.0.0",
)

# The web site runs in the student's browser on a different published port, so
# it is a cross-origin caller. Wide open on purpose: this is a local practice
# environment, not a deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(products_router)
app.include_router(sales_router)
app.include_router(payments_router)
