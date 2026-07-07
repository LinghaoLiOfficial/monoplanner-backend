from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, template_items

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(template_items.router, tags=["template-items"])
