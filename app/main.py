from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.webhooks.telegram import router as telegram_router
from app.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    logger.info("Application starting up")
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title="Telegram Conversation Platform",
    version="0.1.0",
    lifespan=lifespan,
)


# Health endpoint (Section 24)
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


# Mount webhook router
app.include_router(telegram_router)


# Global exception handler to prevent leaking stack traces (Section 26)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception processing %s %s: %s",
        request.method,
        request.url.path,
        str(exc),
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
