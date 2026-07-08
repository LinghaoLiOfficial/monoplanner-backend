from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    blueprints,
    generation,
    health,
    projects,
    requirements,
    template_items,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(requirements.router, tags=["requirements"])
api_router.include_router(blueprints.router, tags=["blueprints"])
api_router.include_router(generation.router, tags=["generation"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(template_items.router, tags=["template-items"])
