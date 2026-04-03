"""FastAPI application factory for PyEDI Portal."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="PyEDI Portal",
        description="Web interface for pyedi-core EDI/CSV/XML processing",
        version="0.1.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5174", "http://localhost:3000", "http://localhost:15174"],
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
    from .routes.compare import router as compare_router
    from .routes.onboard import router as onboard_router
    from .routes.rules import router as rules_router

    application.include_router(validate_router)
    application.include_router(pipeline_router)
    application.include_router(test_router)
    application.include_router(manifest_router)
    application.include_router(config_router)
    application.include_router(compare_router)
    application.include_router(onboard_router)
    application.include_router(rules_router)

    # Serve static build if it exists (production mode)
    static_dir = Path(__file__).parent.parent / "ui" / "dist"
    if static_dir.exists():
        application.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return application


app = create_app()
