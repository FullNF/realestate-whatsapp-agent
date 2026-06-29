import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.webhook import router as webhook_router
from app.config import settings
from app.core.logging_config import configure_logging
from app.db.session import init_db

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version="0.1.0")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Starting %s (env=%s)", settings.APP_NAME, settings.ENV)
    logger.info("Service areas: %s", settings.service_areas_list)
    init_db()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME}


app.include_router(webhook_router, tags=["whatsapp"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.mount("/admin-ui", StaticFiles(directory="static", html=True), name="admin-ui")
