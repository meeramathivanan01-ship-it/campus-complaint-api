import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import init_db
from app.logging_config import configure_logging
from app.routers.auth import router as auth_router
from app.routers.complaints import router as complaints_router

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Campus Complaint & Maintenance Management API",
    description="API for managing campus complaints, maintenance requests, assignments, and follow-up feedback.",
    version="0.1.0",
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    if isinstance(exc.detail, str):
        content = {"error": exc.detail, "status_code": exc.status_code}
    else:
        content = {
            "error": "Request failed",
            "status_code": exc.status_code,
            "detail": jsonable_encoder(exc.detail),
        }
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    details = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": "Request validation failed",
            "status_code": 422,
            "detail": jsonable_encoder(details),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "Unhandled application exception",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500},
    )

app.include_router(complaints_router, prefix="/complaints")
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])


@app.on_event("startup")
def initialize_database() -> None:
    if not settings.secret_key:
        raise RuntimeError("SECRET_KEY environment variable must be configured.")
    logger.info("Application startup (environment=%s)", settings.environment)
    init_db()
    logger.info("Database initialization completed")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Campus Complaint & Maintenance Management API is running."}
