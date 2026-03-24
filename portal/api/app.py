"""FastAPI application factory for PyEDI Portal."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="PyEDI Portal",
        description="Web interface for pyedi-core EDI/CSV/XML processing",
        version="0.1.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    from .routes.validate import router as validate_router
    from .routes.pipeline import router as pipeline_router
    from .routes.test import router as test_router
    from .routes.manifest import router as manifest_router
    from .routes.config import router as config_router

    application.include_router(validate_router)
    application.include_router(pipeline_router)
    application.include_router(test_router)
    application.include_router(manifest_router)
    application.include_router(config_router)

    return application


app = create_app()
